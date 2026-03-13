/**
 * tech-tree.js - "Plague Inc." 风格横向科技树流程图
 * SVG + DOM 混合渲染：SVG 画曲线和粒子，DOM 做可交互节点
 */

const TechTree = {
    _config: {},
    _schema: {},
    _modified: {},
    _floaters: {},
    _activeStepId: null,
    _viewLevel: 0,
    _currentPipelineId: null,
    _currentStageId: null,
    _stepLayout: {},

    // DOM references
    _viewport: null,
    _svgLevel0: null,
    _nodesLevel0: null,
    _bgLevel1: null,
    _svgLevel1: null,
    _nodesLevel1: null,
    _svgParticles: null,
    
    _tooltip: null,
    _nodeElements: {},
    _stepElements: {},
    _layout: {},
    _level0Paths: [],

    // Particle system
    _particles: [],
    _particleRunning: false,
    _particleRafId: null,
    _particleLastTime: 0,
    _particlePaths: [],

    // Layout constants
    STAGE_H_GAP: 260,
    PIPELINE_V_GAP: 280,
    LEFT_MARGIN: 200,
    TOP_MARGIN: 140,
    WAVE_AMP: 60,
    WAVE_FREQ: 0.65,

    // ==================== Init ====================

    async init() {
        console.log('TechTree.init() 开始');
        const canvas = document.getElementById('tech-tree-canvas');
        if (!canvas) { console.error('未找到 tech-tree-canvas 元素'); return; }
        canvas.innerHTML = '';
        this._modified = {};
        this._activeStepId = null;
        this._viewLevel = 0;
        this._currentPipelineId = null;
        this._currentStageId = null;
        this._nodeElements = {};
        this._stepElements = {};
        this._stopParticles();
        Object.keys(this._floaters).forEach(k => this._closePromptFloater(k));

        // Pan state
        this._panX = 0;
        this._panY = 0;
        this._baseTranslateX = 0;
        this._baseTranslateY = 0;
        this._baseScale = 1;
        this._isDragging = false;

        await this._loadConfig();
        console.log('配置加载完成');
        this._buildDOM(canvas);
        console.log('DOM构建完成');
        try { 
            this._renderOverview(); 
            console.log('概览渲染完成');
        } catch (e) { 
            console.error('渲染概览失败:', e); 
            console.error('错误堆栈:', e.stack);
        }
        this._bindGlobalEvents();
        this._initCanvasPan();
        console.log('全局事件绑定完成');
    },

    async _loadConfig() {
        console.log('_loadConfig() 开始');
        try {
            const res = await Api.getConfig();
            console.log('Api.getConfig() 响应:', res);
            if (res.ok) {
                this._config = res.config || {};
                this._schema = res.schema || {};
                console.log('配置加载成功，配置键数量:', Object.keys(this._config).length);
                console.log('模式键数量:', Object.keys(this._schema).length);
            } else {
                console.warn('配置加载失败:', res.msg);
            }
        } catch (error) {
            console.error('_loadConfig() 异常:', error);
        }
        console.log('_loadConfig() 完成');
    },

    getVal(key) {
        if (key in this._modified) return this._modified[key];
        if (key in this._config) return this._config[key];
        const s = this._schema[key];
        return s ? s.default : undefined;
    },

    setVal(key, val) {
        this._modified[key] = val;
        this._updateSaveButton();
        this._updateAllStatuses();
    },

    hasChanges() { return Object.keys(this._modified).length > 0; },

    async save() {
        if (!this.hasChanges()) return;
        const merged = { ...this._config, ...this._modified };
        const res = await Api.reloadPlugin(merged);
        if (res.ok) {
            this._config = merged;
            this._modified = {};
            this._updateSaveButton();
            Utils.toast('配置已保存，插件重启成功', 'success');
        } else {
            Utils.toast(res.msg || '保存失败', 'error');
        }
    },

    async reload() {
        const ok = await Utils.confirm('确认重启插件？未保存的修改将丢失。');
        if (!ok) return;
        const res = await Api.reloadPlugin(null);
        if (res.ok) {
            this._modified = {};
            this._updateSaveButton();
            Utils.toast('插件重启成功', 'success');
            await this._loadConfig();
            if (this._viewLevel === 0) this._renderOverview();
            else {
                this._zoomToOverview(); // safe fallback
            }
        } else {
            Utils.toast(res.msg || '重启失败', 'error');
        }
    },

    _updateSaveButton() {
        const btn = document.getElementById('btn-save-config');
        if (btn) btn.classList.toggle('hidden', !this.hasChanges());
    },

    // ==================== DOM scaffolding ====================

    _buildDOM(canvas) {
        const viewport = document.createElement('div');
        viewport.id = 'flow-viewport';
        this._viewport = viewport;

        const createSVG = (id, zIndex) => {
            const svgNS = 'http://www.w3.org/2000/svg';
            const svg = document.createElementNS(svgNS, 'svg');
            svg.id = id;
            svg.setAttribute('class', 'flow-layer-svg');
            svg.style.zIndex = zIndex;
            return svg;
        };
        const createDiv = (id, zIndex) => {
            const div = document.createElement('div');
            div.id = id;
            div.className = 'flow-layer-div';
            div.style.zIndex = zIndex;
            return div;
        };

        this._svgLevel0 = createSVG('flow-svg-level0', 1);
        this._bgLevel1 = createDiv('flow-bg-level1', 2);
        this._svgLevel1 = createSVG('flow-svg-level1', 3);
        this._svgParticles = createSVG('flow-svg-particles', 4);
        this._nodesLevel0 = createDiv('flow-nodes-level0', 5);
        this._nodesLevel1 = createDiv('flow-nodes-level1', 6);

        // Defs
        const svgNS = 'http://www.w3.org/2000/svg';
        const defs = document.createElementNS(svgNS, 'defs');
        const red = '#e02020';
        defs.innerHTML = `
            <filter id="line-glow" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur in="SourceGraphic" stdDeviation="1.5" result="blur"/>
                <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
            <filter id="particle-glow" x="-100%" y="-100%" width="300%" height="300%">
                <feGaussianBlur in="SourceGraphic" stdDeviation="2" result="blur"/>
                <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
            <radialGradient id="particle-gradient" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stop-color="${red}" stop-opacity="0.6"/>
                <stop offset="100%" stop-color="${red}" stop-opacity="0"/>
            </radialGradient>
            <marker id="arrow" viewBox="0 0 10 6" refX="10" refY="3" markerWidth="7" markerHeight="4" orient="auto">
                <path d="M 0 0 L 10 3 L 0 6 z" class="conn-arrow"/>
            </marker>
        `;
        this._svgLevel0.appendChild(defs);

        // Duplicate defs into svgLevel1 so step connections can reference
        // filters/markers without cross-SVG url() issues in some browsers
        const defs1 = document.createElementNS(svgNS, 'defs');
        defs1.innerHTML = `
            <filter id="step-line-glow" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur in="SourceGraphic" stdDeviation="1.5" result="blur"/>
                <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
            <marker id="step-arrow" viewBox="0 0 10 6" refX="10" refY="3" markerWidth="7" markerHeight="4" orient="auto">
                <path d="M 0 0 L 10 3 L 0 6 z" class="conn-arrow"/>
            </marker>
        `;
        this._svgLevel1.appendChild(defs1);

        ['svg-connections', 'svg-crosslinks'].forEach(id => {
            const g = document.createElementNS(svgNS, 'g'); g.id = id; this._svgLevel0.appendChild(g);
        });
        const gSteps = document.createElementNS(svgNS, 'g'); gSteps.id = 'svg-step-connections'; this._svgLevel1.appendChild(gSteps);
        const gPart = document.createElementNS(svgNS, 'g'); gPart.id = 'svg-particles'; this._svgParticles.appendChild(gPart);

        viewport.appendChild(this._svgLevel0);
        viewport.appendChild(this._nodesLevel0);
        viewport.appendChild(this._bgLevel1);
        viewport.appendChild(this._svgLevel1);
        viewport.appendChild(this._nodesLevel1);
        viewport.appendChild(this._svgParticles);

        canvas.appendChild(viewport);

        // Tooltip
        const tooltip = document.createElement('div');
        tooltip.className = 'flow-tooltip';
        tooltip.innerHTML = '<div class="flow-tooltip-name"></div><div class="flow-tooltip-desc"></div>';
        canvas.appendChild(tooltip);
        this._tooltip = tooltip;
    },

    _setSVGSize(w, h) {
        [this._svgLevel0, this._svgLevel1, this._svgParticles].forEach(svg => {
            svg.setAttribute('width', w);
            svg.setAttribute('height', h);
        });
        [this._nodesLevel0, this._bgLevel1, this._nodesLevel1].forEach(div => {
            div.style.width = w + 'px';
            div.style.height = h + 'px';
        });
        this._viewport.style.width = w + 'px';
        this._viewport.style.height = h + 'px';
    },

    _clearLevel0() {
        this._stopParticles();
        ['svg-connections', 'svg-crosslinks'].forEach(id => {
            const g = this._svgLevel0.querySelector('#' + id);
            if (g) g.innerHTML = '';
        });
        this._nodesLevel0.innerHTML = '';
        this._nodeElements = {};
        this._level0Paths = [];
    },

    // ==================== Level 0: Overview ====================

    _renderOverview() {
        console.log('_renderOverview() 开始');
        this._clearLevel0();
        this._viewLevel = 0;
        this._closeConfigPanel();

        const canvas = document.getElementById('tech-tree-canvas');
        if (canvas) { canvas.scrollTop = 0; canvas.scrollLeft = 0; }

        const pipelines = FlowData.pipelines;
        console.log('流水线数据:', pipelines);
        console.log('流水线数量:', pipelines.length);
        const layout = {};
        let maxX = 0;

        pipelines.forEach((pipeline, pi) => {
            const baseY = this.TOP_MARGIN + pi * this.PIPELINE_V_GAP;
            pipeline.stages.forEach((stage, si) => {
                const x = this.LEFT_MARGIN + si * this.STAGE_H_GAP;
                const waveY = this.WAVE_AMP * Math.sin(si * this.WAVE_FREQ);
                const y = baseY + waveY;
                layout[stage.id] = { x, y, pipelineId: pipeline.id };
                if (x > maxX) maxX = x;
            });
        });
        this._layout = layout;

        const totalW = maxX + 300;
        const totalH = this.TOP_MARGIN + pipelines.length * this.PIPELINE_V_GAP + this.WAVE_AMP + 100;
        this._setSVGSize(Math.max(totalW, 1200), Math.max(totalH, 800));

        pipelines.forEach((pipeline, pi) => {
            const baseY = this.TOP_MARGIN + pi * this.PIPELINE_V_GAP;
            const label = document.createElement('div');
            label.className = 'pipeline-title';
            if (pipeline.disabled) label.style.opacity = '0.3';
            label.style.left = '20px';
            label.style.top = (baseY - this.WAVE_AMP - 70) + 'px';
            label.innerHTML = `<span class="pipeline-title-icon">${pipeline.icon}</span>${pipeline.name}<span class="pipeline-title-sub">${pipeline.desc}</span>`;
            this._nodesLevel0.appendChild(label);
        });

        pipelines.forEach(pipeline => {
            pipeline.stages.forEach(stage => {
                const pos = layout[stage.id];
                const el = this._createStageNode(stage, pipeline, pos);
                this._nodesLevel0.appendChild(el);
                this._nodeElements[stage.id] = el;
            });
        });

        const svgNS = 'http://www.w3.org/2000/svg';
        const gConn = this._svgLevel0.querySelector('#svg-connections');
        const allPaths = [];

        pipelines.forEach(pipeline => {
            if (pipeline.disabled) return;
            const pipelinePaths = [];
            for (let i = 0; i < pipeline.stages.length - 1; i++) {
                const s1 = pipeline.stages[i];
                const s2 = pipeline.stages[i + 1];
                const p1 = layout[s1.id];
                const p2 = layout[s2.id];
                if (!p1 || !p2) continue;

                const cx = (p2.x - p1.x) * 0.4;
                const d = `M ${p1.x} ${p1.y} C ${p1.x + cx} ${p1.y}, ${p2.x - cx} ${p2.y}, ${p2.x} ${p2.y}`;

                const path = document.createElementNS(svgNS, 'path');
                path.setAttribute('d', d);
                path.setAttribute('class', 'conn-path');
                path.setAttribute('marker-end', 'url(#arrow)');
                gConn.appendChild(path);
                pipelinePaths.push(path);
            }
            allPaths.push({ pipelineId: pipeline.id, paths: pipelinePaths });
        });

        this._renderCrossLinks(layout);
        console.log('交叉链接渲染完成');
        this._level0Paths = allPaths;
        console.log('路径数组:', allPaths);
        console.log('路径数量:', allPaths.length);
        this._renderOverviewParticles();
        console.log('粒子渲染完成');
        this._renderBreadcrumb();
        console.log('_renderOverview() 完成');
    },
    
    _renderOverviewParticles() {
        console.log('_renderOverviewParticles() 调用');
        console.log('_level0Paths:', this._level0Paths);
        console.log('_level0Paths长度:', this._level0Paths ? this._level0Paths.length : 0);
        
        // 确保_level0Paths已经被填充
        if (!this._level0Paths || this._level0Paths.length === 0) {
            console.warn('_level0Paths为空，尝试重新收集路径');
            // 重新收集路径
            const gConn = this._svgLevel0.querySelector('#svg-connections');
            if (gConn) {
                const paths = Array.from(gConn.querySelectorAll('.conn-path'));
                if (paths.length > 0) {
                    this._level0Paths = [{
                        pipelineId: 'main',
                        paths: paths
                    }];
                    console.log('重新收集到路径数量:', paths.length);
                }
            }
        }
        
        if (this._level0Paths && this._level0Paths.length > 0) {
            console.log('开始粒子动画');
            this._startParticlesOnPaths(this._level0Paths);
        } else {
            console.warn('_level0Paths仍为空，粒子动画未启动');
        }
    },

    _createStageNode(stage, pipeline, pos) {
        const el = document.createElement('div');
        el.className = 'flow-node flow-node--stage';
        el.dataset.nodeId = stage.id;
        el.style.left = pos.x + 'px';
        el.style.top = pos.y + 'px';

        if (pipeline.disabled) el.classList.add('flow-node--disabled');

        const stats = this._calcStageStats(stage);
        if (!pipeline.disabled) {
            if (stats.total > 0 && stats.enabled === stats.total) el.classList.add('flow-node--enabled');
            else if (stats.enabled > 0) el.classList.add('flow-node--partial');
        }

        const card = document.createElement('div');
        card.className = 'stage-card';

        const icon = document.createElement('div');
        icon.className = 'stage-card-icon';
        icon.textContent = stage.icon;
        card.appendChild(icon);

        const name = document.createElement('div');
        name.className = 'stage-card-name';
        name.textContent = stage.name;
        card.appendChild(name);

        const statusBar = document.createElement('div');
        statusBar.className = 'stage-card-status';
        if (!pipeline.disabled) {
            if (stats.total === 0) {
                statusBar.style.background = 'var(--accent-gray)';
                statusBar.style.opacity = '0.4';
            } else if (stats.enabled === stats.total) {
                statusBar.style.background = 'var(--accent-green)';
                statusBar.style.opacity = '0.7';
            } else if (stats.enabled > 0) {
                statusBar.style.background = 'var(--accent-orange)';
                statusBar.style.opacity = '0.6';
            } else {
                statusBar.style.background = 'var(--accent-gray)';
                statusBar.style.opacity = '0.4';
            }
        }
        card.appendChild(statusBar);
        el.appendChild(card);

        if (!pipeline.disabled) {
            el.addEventListener('click', () => {
                console.log(`阶段节点被点击: ${stage.name} (${stage.id})`);
                this._zoomToStage(pipeline.id, stage.id);
            });
            el.addEventListener('mouseenter', (e) => this._showTooltip(stage.name, stage.desc, e));
            el.addEventListener('mouseleave', () => this._hideTooltip());
        } else {
            console.log(`流水线 ${pipeline.id} 被禁用，不绑定点击事件`);
        }

        return el;
    },

    _renderCrossLinks(layout) {
        const g = this._svgLevel0.querySelector('#svg-crosslinks');
        g.innerHTML = '';
        const svgNS = 'http://www.w3.org/2000/svg';

        FlowData.crossLinks.forEach(link => {
            const fromCtx = FlowData.getStepContext(link.from);
            const toCtx = FlowData.getStepContext(link.to);
            if (!fromCtx || !toCtx) {
                console.warn(`交叉链接步骤未找到: from=${link.from}, to=${link.to}`);
                console.warn(`  from步骤: ${link.from}, to步骤: ${link.to}`);
                return;
            }

            const p1 = layout[fromCtx.stage.id];
            const p2 = layout[toCtx.stage.id];
            if (!p1 || !p2) {
                console.warn(`交叉链接阶段位置未找到: fromStage=${fromCtx.stage.id}, toStage=${toCtx.stage.id}`);
                return;
            }

            // 计算连接点：从fromStage的底部到toStage的顶部
            const x1 = p1.x;
            const y1 = p1.y + 55;  // 阶段卡片底部
            const x2 = p2.x;
            const y2 = p2.y - 55;  // 阶段卡片顶部

            // 使用贝塞尔曲线连接
            const my = (y1 + y2) / 2;
            const d = `M ${x1} ${y1} C ${x1 + 30} ${my}, ${x2 - 30} ${my}, ${x2} ${y2}`;

            const path = document.createElementNS(svgNS, 'path');
            path.setAttribute('d', d);
            path.setAttribute('class', 'cross-link-path');
            g.appendChild(path);

            // 在曲线中点添加标签
            const mx = (x1 + x2) / 2;
            const labelY = my;
            const labelText = link.label || '链接';
            
            // 根据中文字符数量计算标签宽度（中文字符约12px宽）
            const textLen = Math.max(labelText.length * 12 + 16, 80);
            
            const bg = document.createElementNS(svgNS, 'rect');
            bg.setAttribute('x', mx - textLen / 2);
            bg.setAttribute('y', labelY - 10);
            bg.setAttribute('width', textLen);
            bg.setAttribute('height', 18);
            bg.setAttribute('class', 'cross-link-label-bg');
            g.appendChild(bg);

            const text = document.createElementNS(svgNS, 'text');
            text.setAttribute('x', mx);
            text.setAttribute('y', labelY + 4);
            text.setAttribute('text-anchor', 'middle');
            text.setAttribute('class', 'cross-link-label');
            text.textContent = labelText;
            g.appendChild(text);
            
            console.log(`渲染交叉链接: ${link.label} (${link.from} → ${link.to})`);
            console.log(`  位置: (${x1}, ${y1}) → (${x2}, ${y2})`);
        });
    },

    /**
     * 判断单个步骤是否"有效激活"
     * 规则：
     *   1. internal 步骤不参与统计
     *   2. 若有 parentToggle 且其值为 false → 步骤无论自身开关如何都算"未激活"
     *   3. 若有 toggle → 取其值
     *   4. 若有 activeIfAny（列表/bool型键数组）→ 至少一个键为 true 或非空列表才算激活
     *   5. 若无 toggle/activeIfAny（纯配置型步骤）→ 默认始终激活
     */
    _isStepEffectivelyEnabled(step) {
        if (step.internal) return null; // 不参与
        if (step.parentToggle && !this.getVal(step.parentToggle)) return false;
        if (step.toggle) return !!this.getVal(step.toggle);
        if (step.activeIfAny && step.activeIfAny.length > 0) {
            return step.activeIfAny.some(k => {
                const v = this.getVal(k);
                return Array.isArray(v) ? v.length > 0 : !!v;
            });
        }
        return true; // 无 toggle/activeIfAny 的配置步骤默认激活
    },

    _calcStageStats(stage) {
        let total = 0, enabled = 0;
        for (const step of stage.steps) {
            const state = this._isStepEffectivelyEnabled(step);
            if (state === null) continue; // internal 跳过
            total++;
            if (state) enabled++;
        }
        return { total, enabled };
    },

    // ==================== Level 1: Zoom to Stage & Steps ====================

    _zoomToStage(pipelineId, stageId) {
        console.log(`_zoomToStage: pipelineId=${pipelineId}, stageId=${stageId}`);
        this._viewLevel = 1;
        this._currentPipelineId = pipelineId;
        this._currentStageId = stageId;
        this._activeStepId = null;
        this._closeConfigPanel();

        const stage = FlowData.getStageById(stageId);
        const stagePos = this._layout[stageId];
        console.log('阶段对象:', stage);
        console.log('阶段位置:', stagePos);
        if (!stage || !stagePos) {
            console.warn('未找到阶段或阶段位置，退出');
            return;
        }

        // Fade out unrelated level 0
        Object.entries(this._nodeElements).forEach(([id, el]) => {
            if (id !== stageId) {
                el.style.opacity = '0.1';
                el.style.pointerEvents = 'none';
            } else {
                el.style.opacity = '1';
                el.classList.add('stage-zoomed');
                el.style.zIndex = '100';
            }
        });
        this._svgLevel0.style.opacity = '0.1';
        this._nodesLevel0.querySelectorAll('.pipeline-title').forEach(el => el.style.opacity = '0');

        this._renderStepsForStage(stage, stagePos);
        this._focusOnStageAndSteps(stagePos);
        this._renderBreadcrumb();
    },

    _renderStepsForStage(stage, stagePos) {
        const steps = stage.steps;
        const count = steps.length;
        const canvas = document.getElementById('tech-tree-canvas');
        const vw = canvas.clientWidth || 1200;
        const vh = canvas.clientHeight || 800;

        const S = 1.15; // Smooth zoom scale
        const availW = (vw * 0.7) / S; 
        const availH = (vh * 0.6) / S; 

        // Start step flow slightly to the right of the stage
        const startX = stagePos.x + 90; 
        const startY = stagePos.y;

        // Clear Level 1
        this._nodesLevel1.innerHTML = '';
        this._bgLevel1.innerHTML = '';
        this._svgLevel1.querySelector('#svg-step-connections').innerHTML = '';
        this._stepElements = {};
        this._stepLayout = {};

        // Wavy layout for steps
        const layout = [];
        const MAX_PER_ROW = 5;
        if (count <= MAX_PER_ROW) {
            for(let i=0; i<count; i++) {
                const progress = count > 1 ? i / (count - 1) : 0.5;
                const x = startX + progress * availW;
                const wave = Math.sin(progress * Math.PI) * (availH * 0.25);
                const y = startY + wave;
                layout.push({x, y});
            }
        } else {
            const rows = Math.ceil(count / MAX_PER_ROW);
            const rowH = availH / Math.max(1, (rows - 1));
            for(let i=0; i<count; i++) {
                const row = Math.floor(i / MAX_PER_ROW);
                const colInRow = i % MAX_PER_ROW;
                const itemsInThisRow = (row < rows - 1) ? MAX_PER_ROW : (count - row * MAX_PER_ROW);
                const isReversed = row % 2 === 1;
                const progress = itemsInThisRow > 1 ? colInRow / (itemsInThisRow - 1) : 0.5;
                
                let xProg = isReversed ? (1 - progress) : progress;
                const x = startX + xProg * availW;
                const localWave = Math.sin(progress * Math.PI) * (rowH * 0.3);
                const y = startY + row * rowH + localWave * (isReversed ? -1 : 1);
                layout.push({x, y});
            }
        }

        // Ensure SVG/layer sizes accommodate step positions
        if (layout.length > 0) {
            const maxStepX = Math.max(...layout.map(p => p.x));
            const maxStepY = Math.max(...layout.map(p => p.y));
            const neededW = maxStepX + 300;
            const neededH = maxStepY + 300;
            const currentW = parseInt(this._svgLevel1.getAttribute('width')) || 0;
            const currentH = parseInt(this._svgLevel1.getAttribute('height')) || 0;
            if (neededW > currentW || neededH > currentH) {
                this._setSVGSize(Math.max(neededW, currentW), Math.max(neededH, currentH));
            }
        }

        const svgNS = 'http://www.w3.org/2000/svg';
        const gSteps = this._svgLevel1.querySelector('#svg-step-connections');
        const stepPathElements = [];

        // Connect Stage to first Step
        if (layout.length > 0) {
            const d = this._calcStepConnectionPath({x: stagePos.x + 50, y: stagePos.y}, layout[0]);
            const path = document.createElementNS(svgNS, 'path');
            path.setAttribute('d', d);
            path.setAttribute('class', 'step-conn-path');
            path.setAttribute('marker-end', 'url(#step-arrow)');
            gSteps.appendChild(path);
            stepPathElements.push(path);
        }

        steps.forEach((step, i) => {
            const pos = layout[i];

            // Background vignette for each step to mask level 0
            const glow = document.createElement('div');
            glow.className = 'step-bg-glow';
            glow.style.left = pos.x + 'px';
            glow.style.top = pos.y + 'px';
            this._bgLevel1.appendChild(glow);

            const el = this._createStepNode(step, pos, i);
            this._nodesLevel1.appendChild(el);
            this._stepElements[step.id] = el;
            this._stepLayout[step.id] = { x: pos.x, y: pos.y };

            if (i < layout.length - 1) {
                const p1 = layout[i];
                const p2 = layout[i+1];
                const d = this._calcStepConnectionPath(p1, p2);
                const path = document.createElementNS(svgNS, 'path');
                path.setAttribute('d', d);
                path.setAttribute('class', 'step-conn-path');
                path.setAttribute('marker-end', 'url(#step-arrow)');
                path.style.animationDelay = (i * 0.05) + 's';
                gSteps.appendChild(path);
                stepPathElements.push(path);
            }
        });

        if (stepPathElements.length > 0) {
            this._startParticlesOnPaths([{
                pipelineId: this._currentPipelineId + '-steps',
                paths: stepPathElements
            }]);
        }
    },

    _calcStepConnectionPath(p1, p2) {
        const dx = p2.x - p1.x;
        const dy = p2.y - p1.y;

        // SVG filters (objectBoundingBox) compute their region as a
        // percentage of the path's bounding box.  If the bbox has zero
        // width OR zero height (perfectly vertical / horizontal lines),
        // the filter region collapses and the path becomes invisible.
        // We always add a small perpendicular curve to guarantee a
        // non-degenerate bbox in both dimensions.

        if (Math.abs(dy) > 80) {
            // Predominantly vertical — add horizontal curve offset
            const curveX = Math.abs(dx) < 10 ? 30 : 0;
            const my = (p1.y + p2.y) / 2;
            return `M ${p1.x} ${p1.y} C ${p1.x + curveX} ${my}, ${p2.x + curveX} ${my}, ${p2.x} ${p2.y}`;
        } else {
            // Predominantly horizontal — add vertical curve offset
            const cx = Math.abs(dx) * 0.4;
            const signX = dx >= 0 ? 1 : -1;
            const curveY = Math.abs(dy) < 10 ? 25 : 0;
            return `M ${p1.x} ${p1.y} C ${p1.x + signX * cx} ${p1.y + curveY}, ${p2.x - signX * cx} ${p2.y + curveY}, ${p2.x} ${p2.y}`;
        }
    },

    _createStepNode(step, pos, index) {
        const el = document.createElement('div');
        el.className = 'flow-node flow-node--step';
        el.dataset.stepId = step.id;
        el.style.left = pos.x + 'px';
        el.style.top = pos.y + 'px';
        el.style.animationDelay = (index * 0.04) + 's';

        if (step.internal) el.classList.add('internal');
        if (step.disabled) el.classList.add('disabled-step');
        if (this._activeStepId === step.id) el.classList.add('active');
        const stepEffective = this._isStepEffectivelyEnabled(step);
        if (stepEffective) el.classList.add('step-on');

        const card = document.createElement('div');
        card.className = 'step-card';
        card.textContent = step.icon;

        if (!step.internal && !step.disabled) {
            // 所有非 internal、非 disabled 步骤都显示状态点
            const dot = document.createElement('div');
            dot.className = 'step-status-dot ' + (stepEffective ? 'on' : 'off');
            dot.dataset.stepId = step.id;
            card.appendChild(dot);
        }
        el.appendChild(card);

        const label = document.createElement('div');
        label.className = 'step-label';
        const name = document.createElement('div');
        name.className = 'step-label-name';
        name.textContent = step.name;
        label.appendChild(name);

        if (step.keys && step.keys.length > 0 && !step.internal) {
            const gear = document.createElement('span');
            gear.className = 'step-label-gear';
            gear.textContent = '⚙';
            label.appendChild(gear);
        }
        el.appendChild(label);

        if (step.keys && step.keys.length > 0) {
            el.addEventListener('click', (e) => {
                e.stopPropagation();
                this._selectStep(step);
            });
        } else if (step.internal || step.disabled) {
            el.addEventListener('click', (e) => {
                e.stopPropagation();
                this._selectStep(step);
            });
        }

        el.addEventListener('mouseenter', (e) => this._showTooltip(step.name, step.desc, e));
        el.addEventListener('mouseleave', () => this._hideTooltip());

        return el;
    },

    _focusOnStageAndSteps(stagePos) {
        const canvas = document.getElementById('tech-tree-canvas');
        const vw = canvas.clientWidth || 1200;
        const vh = canvas.clientHeight || 800;
        const S = 1.15;

        const count = Object.keys(this._stepElements).length;
        const MAX_PER_ROW = 5;
        const rows = Math.ceil(count / MAX_PER_ROW);
        const availH = (vh * 0.6) / S;

        // Compute visual center of the group
        const groupCenterY = stagePos.y + (rows > 1 ? availH / 2 : 0);

        // Put stage at 15% from left, and group center at 50% height
        const targetX = vw * 0.15;
        const targetY = vh * 0.5;

        this._baseTranslateX = targetX - (stagePos.x * S);
        this._baseTranslateY = targetY - (groupCenterY * S);
        this._baseScale = S;
        this._panX = 0;
        this._panY = 0;
        this._applyViewportTransform();
    },

    _zoomToOverview() {
        this._viewLevel = 0;
        this._currentPipelineId = null;
        this._currentStageId = null;
        this._activeStepId = null;
        this._closeConfigPanel();

        // Restore viewport
        this._baseTranslateX = 0;
        this._baseTranslateY = 0;
        this._baseScale = 1;
        this._panX = 0;
        this._panY = 0;
        this._applyViewportTransform();

        // Restore Level 0
        Object.values(this._nodeElements).forEach(el => {
            el.style.opacity = '1';
            el.style.pointerEvents = 'auto';
            el.classList.remove('stage-zoomed');
            el.style.zIndex = '';
        });
        this._svgLevel0.style.opacity = '1';
        this._nodesLevel0.querySelectorAll('.pipeline-title').forEach(el => el.style.opacity = '1');

        // Clear Level 1
        this._nodesLevel1.innerHTML = '';
        this._bgLevel1.innerHTML = '';
        this._svgLevel1.querySelector('#svg-step-connections').innerHTML = '';
        this._stepElements = {};
        
        this._renderOverviewParticles();
        this._renderBreadcrumb();
    },

    // ==================== Config Panel ====================

    _selectStep(step) {
        this._activeStepId = step.id;
        this._viewLevel = 2;

        Object.entries(this._stepElements).forEach(([id, el]) => {
            el.classList.toggle('active', id === step.id);
        });

        this._openConfigPanel(step);
    },

    _openConfigPanel(step) {
        const panel = document.getElementById('config-panel');
        const title = document.getElementById('config-panel-title');
        const body = document.getElementById('config-panel-body');

        title.textContent = `${step.icon} ${step.name}`;
        panel.classList.remove('hidden');
        panel.classList.add('visible');

        // Internal steps with no configurable keys
        if (step.internal) {
            body.innerHTML = '';
            const hint = document.createElement('div');
            hint.className = 'dep-hint';
            hint.textContent = 'ℹ️ 此为系统内部处理步骤，无需手动配置';
            body.appendChild(hint);
            if (step.desc) {
                const desc = document.createElement('div');
                desc.className = 'dep-hint';
                desc.style.marginTop = '8px';
                desc.style.opacity = '0.7';
                desc.textContent = step.desc;
                body.appendChild(desc);
            }
            return;
        }

        // Disabled steps (e.g. private pipeline not yet available)
        if (step.disabled) {
            body.innerHTML = '';
            const hint = document.createElement('div');
            hint.className = 'dep-hint';
            hint.textContent = '⚠️ 此功能目前未开放，暂时无法配置';
            body.appendChild(hint);
            if (step.desc) {
                const desc = document.createElement('div');
                desc.className = 'dep-hint';
                desc.style.marginTop = '8px';
                desc.style.opacity = '0.7';
                desc.textContent = step.desc;
                body.appendChild(desc);
            }
            // Still show the config fields in disabled state if they exist
            if (step.keys && step.keys.length > 0 && typeof ConfigEditor !== 'undefined') {
                const editorWrap = document.createElement('div');
                body.appendChild(editorWrap);
                ConfigEditor.render(editorWrap, step, this._schema, step.keys[0]);
            }
            return;
        }

        if (typeof ConfigEditor !== 'undefined') {
            ConfigEditor.render(body, step, this._schema, step.keys[0]);
        }
    },

    _closeConfigPanel() {
        const panel = document.getElementById('config-panel');
        if (panel) panel.classList.remove('visible');
        this._activeStepId = null;
        Object.values(this._stepElements).forEach(el => el.classList.remove('active'));
    },

    // ==================== Breadcrumb ====================

    _renderBreadcrumb() {
        const breadcrumb = document.getElementById('flow-breadcrumb');
        if (!breadcrumb) return;

        if (this._viewLevel === 0) {
            breadcrumb.classList.add('hidden');
            breadcrumb.innerHTML = '';
            return;
        }

        breadcrumb.classList.remove('hidden');
        breadcrumb.innerHTML = '';

        const backBtn = document.createElement('span');
        backBtn.className = 'breadcrumb-segment';
        backBtn.innerHTML = '← 返回总览';
        backBtn.addEventListener('click', () => this._zoomToOverview());
        breadcrumb.appendChild(backBtn);

        const sep = document.createElement('span');
        sep.className = 'breadcrumb-separator';
        sep.textContent = '|';
        breadcrumb.appendChild(sep);

        const pipeline = FlowData.getPipelineById(this._currentPipelineId);
        const stage = FlowData.getStageById(this._currentStageId);

        if (pipeline) {
            const seg = document.createElement('span');
            seg.className = 'breadcrumb-segment';
            seg.textContent = `${pipeline.icon} ${pipeline.name}`;
            breadcrumb.appendChild(seg);
        }

        if (stage) {
            const sep2 = document.createElement('span');
            sep2.className = 'breadcrumb-separator';
            sep2.textContent = '›';
            breadcrumb.appendChild(sep2);

            const cur = document.createElement('span');
            cur.className = 'breadcrumb-current';
            cur.textContent = `${stage.icon} ${stage.name}`;
            breadcrumb.appendChild(cur);
        }
    },

    _showTooltip(name, desc, event) {
        if (!this._tooltip) return;
        this._tooltip.querySelector('.flow-tooltip-name').textContent = name;
        this._tooltip.querySelector('.flow-tooltip-desc').textContent = desc;
        this._tooltip.style.left = (event.clientX + 14) + 'px';
        this._tooltip.style.top = (event.clientY + 14) + 'px';
        this._tooltip.classList.add('show');
    },

    _hideTooltip() {
        if (this._tooltip) this._tooltip.classList.remove('show');
    },

    _updateAllStatuses() {
        document.querySelectorAll('.step-status-dot').forEach(dot => {
            const stepId = dot.dataset.stepId;
            const step = FlowData.getNodeById(stepId);
            if (!step) return;
            const effectiveState = this._isStepEffectivelyEnabled(step);
            if (effectiveState === null) return; // internal
            dot.classList.remove('on', 'off');
            dot.classList.add(effectiveState ? 'on' : 'off');
            const parentNode = dot.closest('.flow-node--step');
            if (parentNode) parentNode.classList.toggle('step-on', effectiveState);
        });

        FlowData.pipelines.forEach(pipeline => {
            if (pipeline.disabled) return;
            pipeline.stages.forEach(stage => {
                const el = this._nodeElements[stage.id];
                if (!el) return;
                el.classList.remove('flow-node--enabled', 'flow-node--partial');
                const stats = this._calcStageStats(stage);
                if (stats.total > 0) {
                    if (stats.enabled === stats.total) el.classList.add('flow-node--enabled');
                    else if (stats.enabled > 0) el.classList.add('flow-node--partial');
                }

                const statusBar = el.querySelector('.stage-card-status');
                if (statusBar) {
                    if (stats.total === 0) {
                        statusBar.style.background = 'var(--accent-gray)';
                        statusBar.style.opacity = '0.4';
                    } else if (stats.enabled === stats.total) {
                        statusBar.style.background = 'var(--accent-green)';
                        statusBar.style.opacity = '0.7';
                    } else if (stats.enabled > 0) {
                        statusBar.style.background = 'var(--accent-orange)';
                        statusBar.style.opacity = '0.6';
                    } else {
                        statusBar.style.background = 'var(--accent-gray)';
                        statusBar.style.opacity = '0.4';
                    }
                }
            });
        });
    },

    _startParticlesOnPaths(pipelinePaths) {
        console.log('_startParticlesOnPaths() 调用');
        console.log('pipelinePaths:', pipelinePaths);
        this._stopParticles();
        this._particleRunning = true;
        this._particles = [];
        this._particleLastTime = 0;
        this._particlePaths = pipelinePaths;

        const gParticles = this._svgParticles.querySelector('#svg-particles');
        console.log('gParticles元素:', gParticles);
        if (gParticles) gParticles.innerHTML = '';

        pipelinePaths.forEach(pp => {
            console.log('处理流水线:', pp.pipelineId, '路径数量:', pp.paths.length);
            if (pp.paths.length === 0) return;
            const particle = this._createParticle(gParticles, pp.pipelineId, pp.paths);
            if (particle) this._particles.push(particle);
        });

        console.log('创建的粒子数量:', this._particles.length);
        if (this._particles.length > 0) {
            console.log('启动粒子动画帧');
            this._particleRafId = requestAnimationFrame((t) => this._particleTick(t));
        } else {
            console.warn('没有创建任何粒子，动画未启动');
        }
    },

    _createParticle(container, pipelineId, paths) {
        if (!container) {
            console.warn('粒子容器为空');
            return null;
        }
        if (!paths || paths.length === 0) {
            console.warn(`流水线 ${pipelineId} 没有路径`);
            return null;
        }
        
        const svgNS = 'http://www.w3.org/2000/svg';
        const TRAIL = 8;
        const red = '#e02020';

        let totalLength = 0;
        const pathLengths = paths.map(p => {
            const l = p.getTotalLength();
            totalLength += l;
            return l;
        });
        
        if (totalLength === 0) {
            console.warn(`流水线 ${pipelineId} 路径总长度为0`);
            return null;
        }

        const trailEls = [];
        for (let i = TRAIL - 1; i >= 0; i--) {
            const c = document.createElementNS(svgNS, 'circle');
            c.setAttribute('r', Math.max(1.5, 2.5 - i * 0.12));
            c.setAttribute('fill', red);
            c.setAttribute('opacity', Math.max(0.05, 0.25 - i * 0.028));
            c.setAttribute('class', 'particle-trail');
            c.setAttribute('cx', '-200');
            c.setAttribute('cy', '-200');
            container.appendChild(c);
            trailEls.push(c);
        }

        const glow = document.createElementNS(svgNS, 'circle');
        glow.setAttribute('r', '7');
        glow.setAttribute('fill', 'url(#particle-gradient)');
        glow.setAttribute('opacity', '0.35');
        glow.setAttribute('cx', '-200');
        glow.setAttribute('cy', '-200');
        container.appendChild(glow);

        const core = document.createElementNS(svgNS, 'circle');
        core.setAttribute('r', '2.5');
        core.setAttribute('fill', red);
        core.setAttribute('class', 'particle-core');
        core.setAttribute('cx', '-200');
        core.setAttribute('cy', '-200');
        container.appendChild(core);

        console.log(`创建粒子成功: ${pipelineId}, 路径数: ${paths.length}, 总长度: ${totalLength.toFixed(2)}`);
        
        return {
            pipelineId, paths, pathLengths, totalLength,
            progress: Math.random(),
            speed: 0.00012,
            trail: [],
            trailEls, coreEl: core, glowEl: glow,
            _nearTimers: {}
        };
    },

    _particleTick(timestamp) {
        if (!this._particleRunning) return;
        const dt = this._particleLastTime ? Math.min(timestamp - this._particleLastTime, 50) : 16;
        this._particleLastTime = timestamp;

        // Determine which nodes/positions to check for proximity
        const nodePositions = this._viewLevel === 0 ? this._layout : this._stepLayout;
        const nodeElements = this._viewLevel === 0 ? this._nodeElements : this._stepElements;
        const PROXIMITY = 25;

        for (const p of this._particles) {
            p.progress += p.speed * dt;
            if (p.progress >= 1) p.progress -= 1;

            const dist = p.progress * p.totalLength;
            const point = this._getPointAtDist(p.paths, p.pathLengths, dist);

            p.coreEl.setAttribute('cx', point.x);
            p.coreEl.setAttribute('cy', point.y);
            p.glowEl.setAttribute('cx', point.x);
            p.glowEl.setAttribute('cy', point.y);

            p.trail.unshift({ x: point.x, y: point.y });
            if (p.trail.length > p.trailEls.length + 1) p.trail.pop();
            p.trailEls.forEach((el, i) => {
                const t = p.trail[i + 1];
                if (t) { el.setAttribute('cx', t.x); el.setAttribute('cy', t.y); }
                else { el.setAttribute('cx', '-200'); el.setAttribute('cy', '-200'); }
            });

            // Proximity glow: pulse enabled nodes when particle passes through
            for (const [id, pos] of Object.entries(nodePositions)) {
                const dx = point.x - pos.x;
                const dy = point.y - pos.y;
                const d = Math.sqrt(dx * dx + dy * dy);
                if (d < PROXIMITY && !p._nearTimers[id]) {
                    const el = nodeElements[id];
                    if (el) {
                        const isEnabled = el.classList.contains('flow-node--enabled') ||
                                          el.classList.contains('step-on');
                        const isPartial = el.classList.contains('flow-node--partial');
                        if (isEnabled) {
                            this._pulseNode(el, 'green');
                        } else if (isPartial) {
                            this._pulseNode(el, 'orange');
                        }
                    }
                    p._nearTimers[id] = true;
                } else if (d >= PROXIMITY * 3) {
                    delete p._nearTimers[id];
                }
            }
        }

        this._particleRafId = requestAnimationFrame((t) => this._particleTick(t));
    },

    _getPointAtDist(paths, pathLengths, dist) {
        let acc = 0;
        for (let i = 0; i < paths.length; i++) {
            if (acc + pathLengths[i] >= dist) {
                return paths[i].getPointAtLength(dist - acc);
            }
            acc += pathLengths[i];
        }
        return paths[paths.length - 1].getPointAtLength(paths[paths.length - 1].getTotalLength());
    },

    _pulseNode(el, color) {
        const card = el.querySelector('.stage-card') || el.querySelector('.step-card');
        if (!card || card.classList.contains('node-pulsing-green') || card.classList.contains('node-pulsing-orange')) return;
        const cls = color === 'orange' ? 'node-pulsing-orange' : 'node-pulsing-green';
        card.classList.add(cls);
        card.addEventListener('animationend', () => {
            card.classList.remove(cls);
        }, { once: true });
    },

    _stopParticles() {
        this._particleRunning = false;
        if (this._particleRafId) {
            cancelAnimationFrame(this._particleRafId);
            this._particleRafId = null;
        }
        this._particles = [];
    },

    renderPromptPreview(promptKey) {
        const data = PromptData[promptKey];
        const wrap = document.createElement('div');
        wrap.className = 'prompt-preview';
        const toggle = document.createElement('div');
        toggle.className = 'prompt-preview-toggle';
        const left = document.createElement('span');
        left.innerHTML = `<span class="prompt-toggle-icon">▶</span> 📋 ${data.title}`;
        const floatBtn = document.createElement('button');
        floatBtn.className = 'prompt-float-btn';
        floatBtn.textContent = '浮窗查看';
        floatBtn.addEventListener('click', (e) => { e.stopPropagation(); this._openPromptFloater(promptKey); });
        toggle.appendChild(left);
        toggle.appendChild(floatBtn);
        wrap.appendChild(toggle);
        const body = document.createElement('div');
        body.className = 'prompt-preview-body hidden';
        const tip = document.createElement('div');
        tip.className = 'prompt-preview-tip';
        tip.textContent = data.desc;
        body.appendChild(tip);
        const pre = document.createElement('pre');
        pre.className = 'prompt-preview-content';
        pre.textContent = data.content;
        body.appendChild(pre);
        wrap.appendChild(body);
        toggle.addEventListener('click', () => {
            const hidden = body.classList.toggle('hidden');
            toggle.querySelector('.prompt-toggle-icon').textContent = hidden ? '▶' : '▼';
        });
        return wrap;
    },

    _openPromptFloater(promptKey) {
        if (this._floaters[promptKey]) { this._bringFloaterToTop(this._floaters[promptKey]); return; }
        const data = PromptData[promptKey];
        const floater = document.createElement('div');
        floater.className = 'prompt-floater';
        const count = Object.keys(this._floaters).length;
        floater.style.top = (80 + count * 30) + 'px';
        floater.style.left = Math.max(20, window.innerWidth - 580 - count * 30) + 'px';
        const titlebar = document.createElement('div');
        titlebar.className = 'prompt-floater-titlebar';
        const title = document.createElement('span');
        title.className = 'prompt-floater-title';
        title.textContent = '📋 ' + data.title;
        const closeBtn = document.createElement('button');
        closeBtn.className = 'prompt-floater-close';
        closeBtn.textContent = '✕';
        closeBtn.addEventListener('click', () => this._closePromptFloater(promptKey));
        titlebar.appendChild(title);
        titlebar.appendChild(closeBtn);
        floater.appendChild(titlebar);
        const body = document.createElement('div');
        body.className = 'prompt-floater-body';
        const tip = document.createElement('div');
        tip.className = 'prompt-floater-tip';
        tip.textContent = data.desc;
        body.appendChild(tip);
        const pre = document.createElement('pre');
        pre.className = 'prompt-floater-content';
        pre.textContent = data.content;
        body.appendChild(pre);
        floater.appendChild(body);
        floater.addEventListener('mousedown', () => this._bringFloaterToTop(floater));
        this._enableDrag(floater, titlebar);
        document.body.appendChild(floater);
        this._floaters[promptKey] = floater;
        this._bringFloaterToTop(floater);
    },

    _closePromptFloater(promptKey) {
        const el = this._floaters[promptKey];
        if (el) { el.remove(); delete this._floaters[promptKey]; }
    },

    closeAllFloaters() {
        Object.keys(this._floaters).forEach(k => this._closePromptFloater(k));
    },

    _bringFloaterToTop(floater) {
        let maxZ = 9999;
        Object.values(this._floaters).forEach(f => {
            const z = parseInt(f.style.zIndex) || 9999;
            if (z > maxZ) maxZ = z;
        });
        floater.style.zIndex = maxZ + 1;
    },

    _enableDrag(floater, handle) {
        let sX, sY, sL, sT;
        const down = (e) => {
            if (e.target.classList.contains('prompt-floater-close')) return;
            e.preventDefault();
            sX = e.clientX; sY = e.clientY;
            const r = floater.getBoundingClientRect();
            sL = r.left; sT = r.top;
            document.addEventListener('mousemove', move);
            document.addEventListener('mouseup', up);
            this._bringFloaterToTop(floater);
        };
        const move = (e) => {
            floater.style.left = (sL + e.clientX - sX) + 'px';
            floater.style.top = (sT + e.clientY - sY) + 'px';
        };
        const up = () => {
            document.removeEventListener('mousemove', move);
            document.removeEventListener('mouseup', up);
        };
        handle.addEventListener('mousedown', down);
    },

    // ==================== Viewport Pan & Transform ====================

    _applyViewportTransform() {
        const tx = this._baseTranslateX + this._panX;
        const ty = this._baseTranslateY + this._panY;
        const s = this._baseScale;
        this._viewport.style.transformOrigin = '0 0';
        this._viewport.style.transform = `translate(${tx}px, ${ty}px) scale(${s})`;
    },

    _initCanvasPan() {
        const canvas = document.getElementById('tech-tree-canvas');
        if (!canvas) return;

        // 阻止配置面板内的滚动事件冒泡到外层
        const configPanel = document.getElementById('config-panel');
        if (configPanel) {
            configPanel.addEventListener('wheel', (e) => {
                e.stopPropagation();
                // 面板内容区滚动到边界时，阻止浏览器把滚动传递给外层
                const body = document.getElementById('config-panel-body');
                if (body) {
                    const atTop = body.scrollTop <= 0 && e.deltaY < 0;
                    const atBottom = body.scrollTop + body.clientHeight >= body.scrollHeight && e.deltaY > 0;
                    if (atTop || atBottom) e.preventDefault();
                }
            }, { passive: false });
        }

        // Mouse wheel → pan
        canvas.addEventListener('wheel', (e) => {
            // Don't intercept when scrolling inside config panel
            if (e.target.closest('.config-panel')) return;
            e.preventDefault();
            this._panX -= e.deltaX;
            this._panY -= e.deltaY;
            // Apply immediately without CSS transition for smooth feel
            const tx = this._baseTranslateX + this._panX;
            const ty = this._baseTranslateY + this._panY;
            const s = this._baseScale;
            this._viewport.style.transition = 'none';
            this._viewport.style.transform = `translate(${tx}px, ${ty}px) scale(${s})`;
            // Restore transition after a tick
            clearTimeout(this._wheelTransitionTimer);
            this._wheelTransitionTimer = setTimeout(() => {
                this._viewport.style.transition = '';
            }, 150);
        }, { passive: false });

        // Middle mouse / left drag on empty area → drag pan
        let dragStartX, dragStartY, dragStartPanX, dragStartPanY;

        const onPointerDown = (e) => {
            // Only left button (0) or middle button (1)
            if (e.button !== 0 && e.button !== 1) return;
            // Don't drag on interactive elements
            if (e.target.closest('.flow-node, .config-panel, .flow-breadcrumb, button, input, select, textarea, .prompt-floater')) return;
            e.preventDefault();
            this._isDragging = true;
            dragStartX = e.clientX;
            dragStartY = e.clientY;
            dragStartPanX = this._panX;
            dragStartPanY = this._panY;
            canvas.style.cursor = 'grabbing';
            this._viewport.style.transition = 'none';
        };

        const onPointerMove = (e) => {
            if (!this._isDragging) return;
            const dx = e.clientX - dragStartX;
            const dy = e.clientY - dragStartY;
            this._panX = dragStartPanX + dx;
            this._panY = dragStartPanY + dy;
            const tx = this._baseTranslateX + this._panX;
            const ty = this._baseTranslateY + this._panY;
            const s = this._baseScale;
            this._viewport.style.transform = `translate(${tx}px, ${ty}px) scale(${s})`;
        };

        const onPointerUp = () => {
            if (!this._isDragging) return;
            this._isDragging = false;
            canvas.style.cursor = '';
            this._viewport.style.transition = '';
        };

        canvas.addEventListener('mousedown', onPointerDown);
        document.addEventListener('mousemove', onPointerMove);
        document.addEventListener('mouseup', onPointerUp);
    },

    _bindGlobalEvents() {
        console.log('_bindGlobalEvents() 开始');
        const btnSave = document.getElementById('btn-save-config');
        console.log('btnSave元素:', btnSave);
        if (btnSave) {
            // 检查按钮样式
            console.log('btnSave样式检查:');
            console.log('- display:', window.getComputedStyle(btnSave).display);
            console.log('- visibility:', window.getComputedStyle(btnSave).visibility);
            console.log('- opacity:', window.getComputedStyle(btnSave).opacity);
            console.log('- pointer-events:', window.getComputedStyle(btnSave).pointerEvents);
            console.log('- cursor:', window.getComputedStyle(btnSave).cursor);
            console.log('- disabled属性:', btnSave.disabled);
            console.log('- hidden类:', btnSave.classList.contains('hidden'));
            
            btnSave.addEventListener('click', () => {
                console.log('保存按钮被点击');
                this.save();
            });
            
            // 添加点击测试
            btnSave.addEventListener('mousedown', (e) => {
                console.log('保存按钮mousedown事件', e);
            });
            btnSave.addEventListener('mouseup', (e) => {
                console.log('保存按钮mouseup事件', e);
            });
        } else {
            console.warn('未找到btn-save-config按钮');
        }

        const btnReload = document.getElementById('btn-reload');
        console.log('btnReload元素:', btnReload);
        if (btnReload) {
            // 检查按钮样式
            console.log('btnReload样式检查:');
            console.log('- display:', window.getComputedStyle(btnReload).display);
            console.log('- visibility:', window.getComputedStyle(btnReload).visibility);
            console.log('- opacity:', window.getComputedStyle(btnReload).opacity);
            console.log('- pointer-events:', window.getComputedStyle(btnReload).pointerEvents);
            console.log('- cursor:', window.getComputedStyle(btnReload).cursor);
            console.log('- disabled属性:', btnReload.disabled);
            console.log('- hidden类:', btnReload.classList.contains('hidden'));
            
            btnReload.addEventListener('click', () => {
                console.log('重启按钮被点击');
                this.reload();
            });
        } else {
            console.warn('未找到btn-reload按钮');
        }

        const btnClose = document.getElementById('btn-close-panel');
        console.log('btnClose元素:', btnClose);
        if (btnClose) {
            btnClose.addEventListener('click', () => {
                console.log('关闭面板按钮被点击');
                this._closeConfigPanel();
                if (this._viewLevel === 2) this._viewLevel = 1;
            });
        }

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                const panel = document.getElementById('config-panel');
                if (panel && panel.classList.contains('visible')) {
                    this._closeConfigPanel();
                    if (this._viewLevel === 2) this._viewLevel = 1;
                } else if (this._viewLevel >= 1) {
                    this._zoomToOverview();
                }
            }
        });
        
        // 检查是否有其他元素覆盖按钮
        console.log('检查按钮位置和尺寸:');
        if (btnSave) {
            const rect = btnSave.getBoundingClientRect();
            console.log('btnSave位置:', rect);
            console.log('btnSave在视口中的位置:', rect.top, rect.left);
            
            // 检查是否有元素在按钮上方
            const elementsAtPoint = document.elementsFromPoint(rect.left + 5, rect.top + 5);
            console.log('按钮上方元素:', elementsAtPoint.slice(0, 3));
        }
        
        console.log('_bindGlobalEvents() 完成');
    }
};
