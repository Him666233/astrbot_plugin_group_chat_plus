/**
 * config-editor.js - 配置表单生成器
 * 根据 schema 类型自动生成编辑控件
 */

const ConfigEditor = {
    _currentNode: null,
    _schema: {},

    _escapeHtml(text) {
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    },

    _getRealEntryNodesByKey(key) {
        if (typeof FlowData === 'undefined' || typeof FlowData.getAllNodes !== 'function') return [];
        const seen = new Set();
        return FlowData.getAllNodes().filter(node => {
            if (!node || !Array.isArray(node.keys) || !node.keys.includes(key)) return false;
            if (node.internal) return false;
            if (seen.has(node.id)) return false;
            seen.add(node.id);
            return true;
        });
    },

    _getStepPath(stepId) {
        if (typeof FlowData === 'undefined' || typeof FlowData.getStepContext !== 'function') return stepId;
        const ctx = FlowData.getStepContext(stepId);
        if (!ctx) return stepId;
        return `${ctx.pipeline.name} → ${ctx.stage.name} → ${ctx.step.name}`;
    },

    _getEffectiveFieldMeta(node, key, sharedMeta, explicitFieldMeta) {
        const entryNodes = this._getRealEntryNodesByKey(key);
        if (entryNodes.length < 2) return null;

        const relatedNodes = entryNodes.map(entry => {
            if (typeof FlowData !== 'undefined' && typeof FlowData.getNodeById === 'function') {
                return FlowData.getNodeById(entry.id) || entry;
            }
            return entry;
        });

        const hasSharedSemantics = !!explicitFieldMeta
            || !!sharedMeta?.isShared
            || relatedNodes.some(entry => {
                if (entry.fieldMeta?.[key]) return true;
                if (entry.sharedConfig?.keys?.includes(key)) return true;
                return !!(entry.shared && entry.sharedFrom);
            });

        if (!hasSharedSemantics) return null;

        const currentPath = this._getStepPath(node.id);
        const otherPaths = entryNodes
            .filter(entry => entry.id !== node.id)
            .map(entry => this._getStepPath(entry.id));
        if (otherPaths.length === 0) return null;

        const badgeText = explicitFieldMeta?.badgeText
            || (sharedMeta?.isShared ? (sharedMeta.badgeText || '共用配置') : '共用配置');
        const tooltipTitle = explicitFieldMeta?.tooltipTitle
            || (sharedMeta?.isShared ? '共用配置说明' : '同一配置项');

        const baseText = explicitFieldMeta?.tooltipText
            || '此项在多个真实配置入口中出现，但它们指向的是同一个真实配置值；在任意一处修改，其他入口都会同步生效。';

        const locationText = otherPaths.length === 1
            ? `当前入口：${currentPath}\n共用入口：${otherPaths[0]}`
            : `当前入口：${currentPath}\n其他共用入口：\n• ${otherPaths.join('\n• ')}`;

        return {
            badgeText,
            tooltipTitle,
            tooltipText: `${baseText}\n\n${locationText}`
        };
    },

    /** 渲染节点的所有配置项到容器 */
    render(container, node, schema, focusKey) {
        container.innerHTML = '';
        this._currentNode = node;
        this._schema = schema;

        const disabled = node.disabled ||
            (node.parentToggle && !TechTree.getVal(node.parentToggle));
        const sharedConfig = node.sharedConfig || null;
        const sharedKeys = sharedConfig?.keys || [];
        const fieldMetaMap = node.fieldMeta || {};

        // 依赖提示
        if (node.parentToggle && !TechTree.getVal(node.parentToggle)) {
            const hint = document.createElement('div');
            hint.className = 'dep-hint';
            const ps = schema[node.parentToggle];
            hint.textContent = `⚠️ 需开启「${ps ? ps.description : node.parentToggle}」才生效`;
            container.appendChild(hint);
        }

        // 共用配置提示横幅
        if (sharedConfig && sharedKeys.length > 0) {
            const banner = document.createElement('div');
            banner.className = 'shared-config-banner';
            banner.innerHTML = `
                <span class="shared-config-banner-icon">🔗</span>
                <span class="shared-config-banner-text">
                    <strong>${sharedConfig.title || '这是一个共用配置'}</strong><br>
                    ${sharedConfig.text || '以下带有「共用」标识的配置项会在多个节点之间同步生效。'}
                </span>`;
            container.appendChild(banner);
        }

        // 只读安全项提示横幅（仅当节点有 readonlyKeys 时显示）
        const readonlyKeys = node.readonlyKeys || [];
        if (readonlyKeys.length > 0) {
            const banner = document.createElement('div');
            banner.className = 'security-readonly-banner';
            banner.innerHTML = `
                <span class="security-readonly-banner-icon">🔒</span>
                <span class="security-readonly-banner-text">
                    以下带有 <strong>🔒</strong> 标识的配置项属于安全敏感设置，出于安全考虑不允许在 Web 端修改。<br>
                    如需调整，请前往 <strong>AstrBot 平台 → 插件配置</strong> 中对应的传统配置项进行修改。
                </span>`;
            container.appendChild(banner);
        }

        node.keys.forEach(key => {
            const s = schema[key];
            if (!s) return;
            const isReadonly = readonlyKeys.includes(key);
            const isShared = sharedKeys.includes(key);
            const sharedMeta = isShared ? {
                isShared: true,
                badgeText: sharedConfig.badgeText || '共用',
                note: sharedConfig.fieldNote || '此项属于共享配置，修改后会同步影响读空气AI、主动对话判断AI、频率判断AI。'
            } : null;
            const explicitFieldMeta = fieldMetaMap[key] || null;
            const fieldMeta = this._getEffectiveFieldMeta(node, key, sharedMeta, explicitFieldMeta);
            const field = isReadonly
                ? this._createReadonlyField(key, s)
                : this._createField(key, s, disabled, sharedMeta, fieldMeta);
            container.appendChild(field);

            // 滚动到聚焦项（仅滚动 config-panel-body，不影响祖先容器）
            if (key === focusKey) {
                requestAnimationFrame(() => {
                    const scrollParent = container;
                    const top = field.offsetTop - scrollParent.offsetTop
                                - (scrollParent.clientHeight - field.offsetHeight) / 2;
                    scrollParent.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });
                });
            }
        });
    },

    /** 创建只读安全配置字段（仅展示当前值，不可编辑） */
    _createReadonlyField(key, schema) {
        const field = document.createElement('div');
        field.className = 'config-field config-field-readonly';

        // 标签（带锁图标）
        const label = document.createElement('div');
        label.className = 'config-field-label';
        label.textContent = '🔒 ' + (schema.description || key).replace(/^[^\s]+\s/, '');
        field.appendChild(label);

        // 当前值展示
        const val = TechTree.getVal(key);
        const valEl = document.createElement('div');
        valEl.className = 'config-field-readonly-value';
        const displayVal = Array.isArray(val)
            ? (val.length === 0 ? '（空列表）' : val.join(', '))
            : (val === '' ? '（空）' : String(val));
        valEl.textContent = `当前值：${displayVal}`;
        field.appendChild(valEl);

        // 安全说明
        const note = document.createElement('div');
        note.className = 'config-field-readonly-note';
        note.textContent = '⚠️ 此项为安全敏感配置，请在 AstrBot 平台插件配置页修改';
        field.appendChild(note);

        return field;
    },

    /** 创建单个配置字段 */
    _createField(key, schema, disabled, sharedMeta = null, fieldMeta = null) {
        const field = document.createElement('div');
        field.className = 'config-field';
        if (disabled) field.classList.add('disabled');
        if (key in TechTree._modified) field.classList.add('modified');
        if (sharedMeta?.isShared) field.classList.add('config-field-shared');

        if (fieldMeta?.badgeText) {
            field.classList.add('config-field-has-tag');
            const tag = document.createElement('div');
            tag.className = 'config-field-tag';
            tag.setAttribute('tabindex', '0');
            tag.setAttribute('role', 'note');
            const tooltipTitle = fieldMeta.tooltipTitle
                ? `<strong>${this._escapeHtml(fieldMeta.tooltipTitle)}</strong>`
                : '';
            const tooltipText = fieldMeta.tooltipText
                ? `<span>${this._escapeHtml(fieldMeta.tooltipText)}</span>`
                : '';
            tag.innerHTML = `
                <span class="config-field-tag-label">${this._escapeHtml(fieldMeta.badgeText)}</span>
                <span class="config-field-tag-tooltip">
                    ${tooltipTitle}
                    ${tooltipText}
                </span>`;
            field.appendChild(tag);
        }

        // 标签
        const label = document.createElement('div');
        label.className = 'config-field-label';
        label.textContent = (schema.description || key).replace(/^[^\s]+\s/, '');
        if (sharedMeta?.isShared) {
            const badge = document.createElement('span');
            badge.className = 'config-shared-badge';
            badge.textContent = sharedMeta.badgeText || '共用';
            label.appendChild(document.createTextNode(' '));
            label.appendChild(badge);
        }
        field.appendChild(label);

        if (sharedMeta?.isShared && sharedMeta.note) {
            const sharedNote = document.createElement('div');
            sharedNote.className = 'config-field-shared-note';
            sharedNote.textContent = sharedMeta.note;
            field.appendChild(sharedNote);
        }

        // 提示
        if (schema.hint) {
            const hint = document.createElement('div');
            hint.className = 'config-field-hint';
            hint.textContent = schema.hint;
            field.appendChild(hint);
            this._setupCollapse(hint);
        }

        // 根据类型生成控件
        const val = TechTree.getVal(key);
        switch (schema.type) {
            case 'bool':
                field.appendChild(this._boolControl(key, val));
                break;
            case 'int':
            case 'float':
                field.appendChild(this._numberControl(key, val, schema));
                break;
            case 'string':
                if (schema.options) {
                    field.appendChild(this._selectControl(key, val, schema));
                } else {
                    field.appendChild(this._stringControl(key, val));
                }
                break;
            case 'text':
                field.appendChild(this._textControl(key, val));
                break;
            case 'list':
                field.appendChild(this._listControl(key, val));
                break;
            default:
                field.appendChild(this._stringControl(key, val));
        }

        // 默认值提示
        if (schema.default !== undefined) {
            if (schema.promptDataRef && typeof PromptData !== 'undefined' && PromptData[schema.promptDataRef]
                && typeof TechTree !== 'undefined' && TechTree.renderPromptPreview) {
                field.appendChild(TechTree.renderPromptPreview(schema.promptDataRef));
            } else {
                const def = document.createElement('div');
                def.className = 'config-field-default';
                const dv = Array.isArray(schema.default)
                    ? JSON.stringify(schema.default)
                    : String(schema.default);
                def.textContent = `默认: ${dv}`;
                field.appendChild(def);
                this._setupCollapse(def);
            }
        }

        return field;
    },

    /** 布尔开关 */
    _boolControl(key, val) {
        const wrap = document.createElement('div');
        wrap.className = 'toggle-wrap';
        const lbl = document.createElement('label');
        lbl.className = 'toggle';
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.checked = !!val;
        input.addEventListener('change', () => TechTree.setVal(key, input.checked));
        const slider = document.createElement('span');
        slider.className = 'toggle-slider';
        lbl.appendChild(input);
        lbl.appendChild(slider);
        wrap.appendChild(lbl);
        return wrap;
    },

    /** 数字输入 */
    _numberControl(key, val, schema) {
        const wrap = document.createElement('div');
        wrap.className = 'number-input-wrap';
        const input = document.createElement('input');
        input.type = 'number';
        input.value = val !== undefined ? val : '';
        if (schema.type === 'float') input.step = '0.01';
        input.addEventListener('change', () => {
            const v = schema.type === 'int' ? parseInt(input.value) : parseFloat(input.value);
            if (!isNaN(v)) TechTree.setVal(key, v);
        });
        wrap.appendChild(input);
        return wrap;
    },

    /** 下拉选择 */
    _selectControl(key, val, schema) {
        const select = document.createElement('select');
        select.className = 'config-select';
        schema.options.forEach(opt => {
            const o = document.createElement('option');
            o.value = opt;
            o.textContent = opt;
            if (opt === val) o.selected = true;
            select.appendChild(o);
        });
        select.addEventListener('change', () => TechTree.setVal(key, select.value));
        return select;
    },

    /** 单行文本 */
    _stringControl(key, val) {
        const input = document.createElement('input');
        input.type = 'text';
        input.value = val !== undefined ? String(val) : '';
        input.addEventListener('change', () => TechTree.setVal(key, input.value));
        return input;
    },

    /** 多行文本 */
    _textControl(key, val) {
        const ta = document.createElement('textarea');
        ta.rows = 4;
        ta.value = val !== undefined ? String(val) : '';
        ta.addEventListener('change', () => TechTree.setVal(key, ta.value));
        // 阻止滚轮事件冒泡到父级，允许在 textarea 内部独立滚动
        ta.addEventListener('wheel', (e) => {
            e.stopPropagation();
        });
        return ta;
    },

    /** 列表编辑器 */
    _listControl(key, val) {
        const list = Array.isArray(val) ? [...val] : [];
        const wrap = document.createElement('div');
        wrap.className = 'list-editor';

        const renderItems = () => {
            wrap.innerHTML = '';
            list.forEach((item, i) => {
                const row = document.createElement('div');
                row.className = 'list-item';
                const input = document.createElement('input');
                input.type = 'text';
                input.value = typeof item === 'object' ? JSON.stringify(item) : String(item);
                input.addEventListener('change', () => {
                    list[i] = this._parseListItem(input.value);
                    TechTree.setVal(key, [...list]);
                });
                const del = document.createElement('button');
                del.className = 'btn-icon';
                del.textContent = '✕';
                del.addEventListener('click', () => {
                    list.splice(i, 1);
                    TechTree.setVal(key, [...list]);
                    renderItems();
                });
                row.appendChild(input);
                row.appendChild(del);
                wrap.appendChild(row);
            });

            // 添加行
            const addRow = document.createElement('div');
            addRow.className = 'list-add-row';
            const addInput = document.createElement('input');
            addInput.type = 'text';
            addInput.placeholder = '添加新项...';
            const addBtn = document.createElement('button');
            addBtn.className = 'btn btn-sm';
            addBtn.textContent = '+';
            addBtn.addEventListener('click', () => {
                if (!addInput.value.trim()) return;
                list.push(this._parseListItem(addInput.value.trim()));
                TechTree.setVal(key, [...list]);
                renderItems();
            });
            addRow.appendChild(addInput);
            addRow.appendChild(addBtn);
            wrap.appendChild(addRow);
        };

        renderItems();
        return wrap;
    },

    /** 尝试解析列表项（JSON 对象或字符串） */
    _parseListItem(str) {
        try {
            const parsed = JSON.parse(str);
            if (typeof parsed === 'object') return parsed;
        } catch {}
        return str;
    },

    /** 为元素设置折叠/展开（渲染后检测实际高度） */
    _setupCollapse(el) {
        requestAnimationFrame(() => {
            const lineHeight = parseFloat(getComputedStyle(el).lineHeight) || 16;
            const fullHeight = el.scrollHeight; // 未折叠时读取真实高度
            if (fullHeight > lineHeight * 4 + 4) {
                el.classList.add('collapsible');
                const btn = document.createElement('span');
                btn.className = 'collapse-toggle';
                btn.textContent = '▼ 展开';
                el.parentNode.insertBefore(btn, el.nextSibling);
                btn.addEventListener('click', () => {
                    if (el.classList.contains('expanded')) {
                        el.style.maxHeight = el.scrollHeight + 'px';
                        el.getBoundingClientRect();
                        el.classList.remove('expanded');
                        el.style.maxHeight = '';
                        btn.textContent = '▼ 展开';
                    } else {
                        el.classList.add('expanded');
                        el.style.maxHeight = fullHeight + 'px';
                        btn.textContent = '▲ 收起';
                    }
                });
                el.addEventListener('click', () => btn.click());
            }
        });
    }
};
