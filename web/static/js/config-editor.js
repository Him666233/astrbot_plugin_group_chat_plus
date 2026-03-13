/**
 * config-editor.js - 配置表单生成器
 * 根据 schema 类型自动生成编辑控件
 */

const ConfigEditor = {
    _currentNode: null,
    _schema: {},

    /** 渲染节点的所有配置项到容器 */
    render(container, node, schema, focusKey) {
        container.innerHTML = '';
        this._currentNode = node;
        this._schema = schema;

        const disabled = node.disabled ||
            (node.parentToggle && !TechTree.getVal(node.parentToggle));

        // 依赖提示
        if (node.parentToggle && !TechTree.getVal(node.parentToggle)) {
            const hint = document.createElement('div');
            hint.className = 'dep-hint';
            const ps = schema[node.parentToggle];
            hint.textContent = `⚠️ 需开启「${ps ? ps.description : node.parentToggle}」才生效`;
            container.appendChild(hint);
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
            const field = isReadonly
                ? this._createReadonlyField(key, s)
                : this._createField(key, s, disabled);
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
    _createField(key, schema, disabled) {
        const field = document.createElement('div');
        field.className = 'config-field';
        if (disabled) field.classList.add('disabled');
        if (key in TechTree._modified) field.classList.add('modified');

        // 标签
        const label = document.createElement('div');
        label.className = 'config-field-label';
        label.textContent = (schema.description || key).replace(/^[^\s]+\s/, '');
        field.appendChild(label);

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
        // Prevent wheel event from bubbling to parent to allow scrolling inside textarea
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
