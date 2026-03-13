/**
 * flow-data.js - 消息处理流水线数据定义
 * 按实际代码执行顺序，将所有配置项映射到流水线各阶段各步骤
 */

const FlowData = {
    _nodeMap: {},   // stepId → step
    _stageMap: {},  // stageId → stage

    pipelines: [
        {
            id: 'main',
            name: '消息处理流水线',
            icon: '💬',
            desc: '群消息从接入到回复的完整处理链路',
            stages: []
        },
        {
            id: 'proactive',
            name: '主动对话流水线',
            icon: '🗣️',
            desc: '群内沉默时主动发起话题的独立流程',
            stages: []
        },
        {
            id: 'private',
            name: '私信功能',
            icon: '📱',
            desc: '⚠️ 此功能目前未开放',
            disabled: true,
            stages: []
        }
    ],

    crossLinks: [
        { from: 'attention-adjust', to: 'proactive-attention', label: '注意力排行共享' },
        { from: 'time-period-adjust', to: 'proactive-time', label: '时间段策略复用' },
        { from: 'base-probability', to: 'proactive-basic', label: '基础概率参考' },
        { from: 'mood-inject', to: 'proactive-gen', label: '情绪状态影响' }
    ],

    init() {
        this.pipelines[0].stages = this._mainStages();
        this.pipelines[1].stages = this._proactiveStages();
        this.pipelines[2].stages = this._privateStages();
        this._buildIndexes();
        return this;
    },

    _buildIndexes() {
        this._nodeMap = {};
        this._stageMap = {};
        for (const pipeline of this.pipelines) {
            for (const stage of pipeline.stages) {
                this._stageMap[stage.id] = stage;
                for (const step of stage.steps) {
                    this._nodeMap[step.id] = step;
                }
            }
        }
    },

    // ==================== 主流水线 ====================

    _mainStages() {
        return [
            this._stageEntry(),
            this._stageTrigger(),
            this._stageProbability(),
            this._stageContent(),
            this._stageAiDecision(),
            this._stageReplyGen(),
            this._stagePostReply()
        ];
    },

    /** Stage 1: 消息接入与预过滤 */
    _stageEntry() {
        return {
            id: 'entry',
            name: '消息接入与预过滤',
            icon: '🚪',
            desc: '群消息进入系统，逐步通过各项过滤器，任一环节不通过则丢弃消息',
            nextStage: 'trigger',
            nextLabel: '通过全部预过滤',
            steps: [
                {
                    id: 'enable-check',
                    name: '群聊总开关',
                    icon: '🔘',
                    desc: '检查群聊功能是否启用，以及当前群是否在启用列表中',
                    toggle: 'enable_group_chat',
                    keys: ['enable_group_chat', 'enabled_groups', 'enable_debug_log'],
                    onFail: 'drop',
                    failLabel: '未启用 → 忽略消息',
                    next: 'user-blacklist'
                },
                {
                    id: 'user-blacklist',
                    name: '用户黑名单',
                    icon: '🚫',
                    desc: '检查发送者是否在黑名单中',
                    toggle: 'enable_user_blacklist',
                    keys: ['enable_user_blacklist', 'blacklist_user_ids'],
                    onFail: 'drop',
                    failLabel: '黑名单用户 → 丢弃',
                    next: 'message-parse'
                },
                {
                    id: 'message-parse',
                    name: '特殊消息解析',
                    icon: '📋',
                    desc: '解析入群欢迎消息和转发合并消息为AI可读文本',
                    activeIfAny: ['enable_welcome_message_parsing', 'enable_forward_message_parsing'],
                    keys: ['enable_welcome_message_parsing', 'welcome_message_mode',
                           'enable_forward_message_parsing', 'forward_max_nesting_depth'],
                    onFail: 'pass',
                    next: 'at-filter'
                },
                {
                    id: 'at-filter',
                    name: '@消息过滤',
                    icon: '📢',
                    desc: '@全体成员消息和@他人消息的过滤规则',
                    activeIfAny: ['enable_ignore_at_all', 'enable_ignore_at_others'],
                    keys: ['enable_ignore_at_all',
                           'enable_ignore_at_others', 'ignore_at_others_mode'],
                    onFail: 'drop',
                    failLabel: '命中@过滤 → 丢弃',
                    next: 'poke-detect'
                },
                {
                    id: 'poke-detect',
                    name: '戳一戳检测',
                    icon: '👆',
                    desc: '检测戳一戳/拍一拍消息，决定处理方式和反戳概率',
                    keys: ['poke_message_mode', 'poke_reverse_on_poke_probability',
                           'poke_enabled_groups'],
                    onFail: 'drop',
                    failLabel: '戳一戳被忽略 → 丢弃',
                    next: 'cmd-filter'
                },
                {
                    id: 'cmd-filter',
                    name: '指令过滤',
                    icon: '⌨️',
                    desc: '识别指令前缀和完整指令，交给指令系统处理',
                    keys: ['enable_command_filter', 'command_prefixes',
                           'enable_full_command_detection', 'full_command_list',
                           'enable_command_prefix_match', 'command_prefix_match_list',
                           'plugin_gcp_reset_allowed_user_ids',
                           'plugin_gcp_reset_here_allowed_user_ids'],
                    onFail: 'passthrough',
                    failLabel: '是指令 → 交给指令系统',
                    next: null
                }
            ]
        };
    },

    /** Stage 2: 触发检测 */
    _stageTrigger() {
        return {
            id: 'trigger',
            name: '触发检测',
            icon: '🎯',
            desc: '检测消息是否包含@、关键词等触发条件，决定后续处理方式',
            nextStage: 'probability',
            nextLabel: '进入概率判定',
            steps: [
                {
                    id: 'trigger-detect',
                    name: '触发条件检测',
                    icon: '🔍',
                    desc: '检测@消息、触发关键词、黑名单关键词',
                    activeIfAny: ['trigger_keywords'],
                    keys: ['trigger_keywords', 'keyword_smart_mode',
                           'blacklist_keywords'],
                    onFail: 'pass',
                    next: 'wait-window'
                },
                {
                    id: 'wait-window',
                    name: '等待窗口',
                    icon: '⏳',
                    desc: '等待用户连续发送多条消息后合并处理，避免逐条回复',
                    toggle: 'enable_group_wait_window',
                    keys: ['enable_group_wait_window', 'group_wait_window_timeout_ms',
                           'group_wait_window_max_extra_messages',
                           'group_wait_window_max_users',
                           'group_wait_window_attention_decay_per_msg',
                           'group_wait_window_merge_at_messages',
                           'group_wait_window_merge_at_list_mode',
                           'group_wait_window_merge_at_user_list'],
                    onFail: 'cache',
                    failLabel: '拦截缓存 → 等待更多消息',
                    next: 'emoji-detect'
                },
                {
                    id: 'emoji-detect',
                    name: '表情包检测',
                    icon: '😀',
                    desc: '识别QQ表情包/贴纸消息，为概率阶段提供衰减标记（仅QQ平台）',
                    internal: true,
                    keys: [],
                    onFail: 'pass',
                    next: null
                }
            ]
        };
    },

    /** Stage 3: 概率判定系统 */
    _stageProbability() {
        return {
            id: 'probability',
            name: '概率判定系统',
            icon: '🎲',
            desc: '多层概率修饰器依次调整回复概率，最终随机判定是否回复',
            nextStage: 'content',
            nextLabel: '概率通过',
            steps: [
                {
                    id: 'base-probability',
                    name: '基础概率',
                    icon: '📊',
                    desc: '初始概率值，回复后临时提升概率，戳一戳跳过概率检查',
                    keys: ['initial_probability', 'after_reply_probability',
                           'probability_duration',
                           'poke_bot_skip_probability',
                           'poke_bot_probability_boost_reference'],
                    onFail: 'pass',
                    next: 'time-period-adjust'
                },
                {
                    id: 'time-period-adjust',
                    name: '时间段调整',
                    icon: '🕐',
                    desc: '按时间段（如深夜低活跃、中午高峰）动态调整概率倍率',
                    toggle: 'enable_dynamic_reply_probability',
                    keys: ['enable_dynamic_reply_probability', 'reply_time_periods',
                           'reply_time_transition_minutes',
                           'reply_time_min_factor', 'reply_time_max_factor',
                           'reply_time_use_smooth_curve'],
                    onFail: 'pass',
                    next: 'attention-adjust'
                },
                {
                    id: 'attention-adjust',
                    name: '注意力机制',
                    icon: '👁️',
                    desc: '追踪多个用户的互动历史，根据注意力分数调整回复概率',
                    toggle: 'enable_attention_mechanism',
                    keys: ['enable_attention_mechanism', 'attention_increased_probability',
                           'attention_decreased_probability', 'attention_duration',
                           'attention_max_tracked_users', 'attention_decay_halflife',
                           'emotion_decay_halflife', 'attention_boost_step',
                           'attention_decrease_step', 'attention_decrease_on_no_reply_step',
                           'attention_decrease_threshold', 'emotion_boost_step',
                           'enable_attention_emotion_detection',
                           'attention_emotion_keywords', 'attention_enable_negation',
                           'attention_negation_words', 'attention_negation_check_range',
                           'attention_positive_emotion_boost',
                           'attention_negative_emotion_decrease'],
                    onFail: 'pass',
                    next: 'attention-spillover'
                },
                {
                    id: 'attention-spillover',
                    name: '注意力溢出',
                    icon: '🌊',
                    desc: '热烈对话时将注意力扩散到其他活跃用户',
                    toggle: 'enable_attention_spillover',
                    parentToggle: 'enable_attention_mechanism',
                    keys: ['enable_attention_spillover', 'attention_spillover_ratio',
                           'attention_spillover_decay_halflife',
                           'attention_spillover_min_trigger'],
                    onFail: 'pass',
                    next: 'attention-cooldown'
                },
                {
                    id: 'attention-cooldown',
                    name: '注意力冷却',
                    icon: '❄️',
                    desc: '防止注意力误判，暂停注意力自动增长',
                    toggle: 'enable_attention_cooldown',
                    parentToggle: 'enable_attention_mechanism',
                    keys: ['enable_attention_cooldown', 'cooldown_max_duration',
                           'cooldown_trigger_threshold', 'cooldown_attention_decrease'],
                    onFail: 'pass',
                    next: 'humanize-mode'
                },
                {
                    id: 'humanize-mode',
                    name: '拟人增强',
                    icon: '🎭',
                    desc: '静默状态机、动态阈值、兴趣话题提升，模拟真人回复节奏',
                    toggle: 'enable_humanize_mode',
                    keys: ['enable_humanize_mode', 'humanize_silent_mode_threshold',
                           'humanize_silent_max_duration', 'humanize_silent_max_messages',
                           'humanize_enable_dynamic_threshold',
                           'humanize_base_message_threshold',
                           'humanize_max_message_threshold',
                           'humanize_include_decision_history',
                           'humanize_interest_keywords',
                           'humanize_interest_boost_probability'],
                    onFail: 'drop',
                    failLabel: '静默模式 → 跳过回复',
                    next: 'fatigue-decay'
                },
                {
                    id: 'fatigue-decay',
                    name: '对话疲劳',
                    icon: '🔄',
                    desc: '追踪与特定用户的连续对话轮次，轮次越多概率越低',
                    toggle: 'enable_conversation_fatigue',
                    parentToggle: 'enable_attention_mechanism',
                    keys: ['enable_conversation_fatigue', 'fatigue_reset_threshold',
                           'fatigue_threshold_light', 'fatigue_threshold_medium',
                           'fatigue_threshold_heavy',
                           'fatigue_probability_decrease_light',
                           'fatigue_probability_decrease_medium',
                           'fatigue_probability_decrease_heavy',
                           'fatigue_closing_probability'],
                    onFail: 'pass',
                    next: 'emoji-decay'
                },
                {
                    id: 'emoji-decay',
                    name: '表情包衰减',
                    icon: '🎭',
                    desc: '表情包/贴纸消息降低触发概率',
                    toggle: 'enable_emoji_filter',
                    keys: ['enable_emoji_filter', 'emoji_probability_decay',
                           'emoji_decay_min_probability'],
                    onFail: 'pass',
                    next: 'density-limit'
                },
                {
                    id: 'density-limit',
                    name: '回复密度限制',
                    icon: '📉',
                    desc: '统计群内Bot总回复次数，接近上限渐进衰减，达到上限完全拦截',
                    toggle: 'enable_reply_density_limit',
                    keys: ['enable_reply_density_limit',
                           'reply_density_window_seconds', 'reply_density_max_replies',
                           'reply_density_soft_limit_ratio', 'reply_density_ai_hint'],
                    onFail: 'pass',
                    next: 'quality-score'
                },
                {
                    id: 'quality-score',
                    name: '消息质量评分',
                    icon: '💎',
                    desc: '本地规则分析消息内容，疑问句提升概率，水消息降低概率',
                    toggle: 'enable_message_quality_scoring',
                    keys: ['enable_message_quality_scoring',
                           'message_quality_question_boost',
                           'message_quality_water_reduce',
                           'message_quality_water_words',
                           'message_quality_question_words'],
                    onFail: 'pass',
                    next: 'frequency-adjust'
                },
                {
                    id: 'frequency-adjust',
                    name: '频率调整器',
                    icon: '📊',
                    desc: 'AI自动分析群内发言频率，动态调整回复概率',
                    toggle: 'enable_frequency_adjuster',
                    keys: ['enable_frequency_adjuster', 'frequency_check_interval',
                           'frequency_analysis_timeout', 'frequency_adjust_duration',
                           'frequency_analysis_message_count',
                           'frequency_min_message_count',
                           'frequency_decrease_factor', 'frequency_increase_factor',
                           'frequency_min_probability', 'frequency_max_probability'],
                    onFail: 'pass',
                    next: 'hard-limit'
                },
                {
                    id: 'hard-limit',
                    name: '概率硬限',
                    icon: '🔒',
                    desc: '强制将最终概率钳位在用户设定的最小/最大范围内',
                    toggle: 'enable_probability_hard_limit',
                    keys: ['enable_probability_hard_limit',
                           'probability_min_limit', 'probability_max_limit'],
                    onFail: 'pass',
                    next: 'random-roll'
                },
                {
                    id: 'random-roll',
                    name: '随机判定',
                    icon: '🎰',
                    desc: '生成随机数与最终概率比较，决定是否继续处理',
                    internal: true,
                    keys: [],
                    onFail: 'drop',
                    failLabel: '概率未通过 → 缓存消息',
                    next: 'prob-cache'
                },
                {
                    id: 'prob-cache',
                    name: '概率过滤缓存',
                    icon: '💾',
                    desc: '概率未通过时，缓存消息文本（含图片描述提取）供后续上下文使用',
                    keys: ['probability_filter_cache_delay',
                           'platform_image_caption_max_wait',
                           'platform_image_caption_retry_interval',
                           'platform_image_caption_fast_check_count'],
                    onFail: 'pass',
                    next: null
                }
            ]
        };
    },

    /** Stage 4: 消息内容处理 */
    _stageContent() {
        return {
            id: 'content',
            name: '消息内容处理',
            icon: '📝',
            desc: '提取和处理消息原始内容，为AI理解做准备',
            nextStage: 'ai-decision',
            nextLabel: '内容处理完成',
            steps: [
                {
                    id: 'image-process',
                    name: '图片处理',
                    icon: '🖼️',
                    desc: '图片转文字(OCR)、多模态识别、平台描述提取、缓存管理',
                    toggle: 'enable_image_processing',
                    keys: ['enable_image_processing', 'image_to_text_scope',
                           'image_to_text_provider_id', 'image_to_text_prompt',
                           'image_to_text_timeout', 'max_images_per_message',
                           'enable_image_description_cache', 'image_description_cache_max_entries',
                           'gcp_clear_image_cache_allowed_user_ids'],
                    onFail: 'pass',
                    next: 'metadata-inject'
                },
                {
                    id: 'metadata-inject',
                    name: '元数据注入',
                    icon: '🏷️',
                    desc: '为消息添加时间戳和发送者信息，帮助AI理解对话上下文',
                    keys: ['include_timestamp', 'include_sender_info'],
                    onFail: 'pass',
                    next: 'context-build'
                },
                {
                    id: 'context-build',
                    name: '上下文构建',
                    icon: '📚',
                    desc: '组装历史消息上下文，控制消息数量和缓存策略',
                    keys: ['max_context_messages', 'custom_storage_max_messages',
                           'pending_cache_max_count', 'pending_cache_ttl_seconds'],
                    onFail: 'pass',
                    next: null
                }
            ]
        };
    },

    /** Stage 5: AI决策判定 */
    _stageAiDecision() {
        return {
            id: 'ai-decision',
            name: 'AI决策判定',
            icon: '🧠',
            desc: '调用AI判断是否应该回复当前消息（读空气）',
            nextStage: 'reply-gen',
            nextLabel: 'AI判定回复',
            steps: [
                {
                    id: 'memory-inject',
                    name: '记忆注入',
                    icon: '🧠',
                    desc: '调用外部记忆插件，将长期记忆注入AI上下文',
                    toggle: 'enable_memory_injection',
                    keys: ['enable_memory_injection', 'memory_plugin_mode',
                           'livingmemory_version', 'livingmemory_top_k',
                           'memory_insertion_timing'],
                    onFail: 'pass',
                    next: 'ai-decide'
                },
                {
                    id: 'ai-decide',
                    name: 'AI读空气决策',
                    icon: '💭',
                    desc: '调用决策AI分析对话上下文，判断是否适合回复',
                    promptDataKey: 'decision-ai',
                    keys: ['decision_ai_provider_id', 'decision_ai_prompt_mode',
                           'decision_ai_extra_prompt', 'decision_ai_timeout'],
                    onFail: 'drop',
                    failLabel: 'AI判定不回复 → 缓存消息',
                    next: 'concurrent-lock'
                },
                {
                    id: 'concurrent-lock',
                    name: '并发锁定',
                    icon: '🔐',
                    desc: '防止同一群组同时处理多条消息导致重复回复',
                    keys: ['concurrent_wait_max_loops', 'concurrent_wait_interval'],
                    onFail: 'pass',
                    next: null
                }
            ]
        };
    },

    /** Stage 6: 回复生成 */
    _stageReplyGen() {
        return {
            id: 'reply-gen',
            name: '回复生成',
            icon: '✍️',
            desc: '注入情绪/工具/记忆上下文，调用AI生成回复，经过多重过滤后输出',
            nextStage: 'post-reply',
            nextLabel: '回复已发送',
            steps: [
                {
                    id: 'mood-inject',
                    name: '情绪注入',
                    icon: '😊',
                    desc: '将Bot当前情绪状态注入提示词，影响回复语气和风格',
                    toggle: 'enable_mood_system',
                    keys: ['enable_mood_system', 'enable_negation_detection',
                           'negation_words', 'negation_check_range',
                           'mood_keywords', 'mood_decay_time',
                           'mood_cleanup_threshold', 'mood_cleanup_interval'],
                    onFail: 'pass',
                    next: 'ai-reply-gen'
                },
                {
                    id: 'ai-reply-gen',
                    name: 'AI回复生成',
                    icon: '✨',
                    desc: '调用AI模型生成回复文本，注入工具提醒和人设',
                    promptDataKey: 'reply-ai',
                    keys: ['reply_ai_prompt_mode', 'reply_ai_extra_prompt',
                           'enable_tools_reminder', 'tools_reminder_persona_filter',
                           'reply_timeout_warning_threshold',
                           'reply_generation_timeout_warning'],
                    onFail: 'pass',
                    next: 'content-filter'
                },
                {
                    id: 'content-filter',
                    name: '内容过滤',
                    icon: '🧹',
                    desc: '过滤输出内容中的敏感词、保存过滤、重复消息拦截',
                    activeIfAny: ['enable_output_content_filter', 'enable_save_content_filter', 'enable_duplicate_filter'],
                    keys: ['enable_output_content_filter', 'output_content_filter_rules',
                           'enable_save_content_filter', 'save_content_filter_rules',
                           'enable_duplicate_filter', 'duplicate_filter_check_count',
                           'enable_duplicate_time_limit', 'duplicate_filter_time_limit'],
                    onFail: 'drop',
                    failLabel: '内容被过滤 → 不发送',
                    next: 'typo-gen'
                },
                {
                    id: 'typo-gen',
                    name: '打字错误模拟',
                    icon: '✏️',
                    desc: '模拟真人打字的错别字，增加自然感',
                    toggle: 'enable_typo_generator',
                    keys: ['enable_typo_generator', 'typo_error_rate',
                           'typo_homophones', 'typo_min_text_length',
                           'typo_min_chinese_chars', 'typo_min_message_length',
                           'typo_min_count', 'typo_max_count'],
                    onFail: 'pass',
                    next: 'typing-delay'
                },
                {
                    id: 'typing-delay',
                    name: '回复延迟',
                    icon: '⏱️',
                    desc: '模拟真人打字速度，按字数计算延迟时间',
                    toggle: 'enable_typing_simulator',
                    keys: ['enable_typing_simulator', 'typing_speed',
                           'typing_max_delay', 'typing_delay_timeout_warning'],
                    onFail: 'pass',
                    next: null
                }
            ]
        };
    },

    /** Stage 7: 回复后处理 */
    _stagePostReply() {
        return {
            id: 'post-reply',
            name: '回复后处理',
            icon: '📤',
            desc: '回复发送后的状态更新、概率提升和附加动作',
            nextStage: null,
            nextLabel: null,
            steps: [
                {
                    id: 'history-save',
                    name: '历史保存',
                    icon: '💾',
                    desc: '将Bot回复保存到对话历史缓存',
                    internal: true,
                    keys: [],
                    onFail: 'pass',
                    next: 'prob-boost'
                },
                {
                    id: 'prob-boost',
                    name: '概率提升',
                    icon: '📈',
                    desc: '回复后临时提升对该群的回复概率（延续对话）',
                    internal: true,
                    keys: [],
                    onFail: 'pass',
                    next: 'poke-after-reply'
                },
                {
                    id: 'poke-after-reply',
                    name: '回复后戳一戳',
                    icon: '👆',
                    desc: '回复后按概率戳一戳发送者，增加互动感',
                    toggle: 'enable_poke_after_reply',
                    keys: ['enable_poke_after_reply', 'poke_after_reply_probability',
                           'poke_after_reply_delay',
                           'enable_poke_trace_prompt', 'poke_trace_max_tracked_users',
                           'poke_trace_ttl_seconds'],
                    onFail: 'pass',
                    next: null
                }
            ]
        };
    },

    // ==================== 主动对话流水线 ====================

    _proactiveStages() {
        return [
            {
                id: 'proactive-trigger',
                name: '触发条件',
                icon: '🔔',
                desc: '检测群内沉默状态，判断是否满足主动对话触发条件',
                nextStage: 'proactive-decide',
                nextLabel: '条件满足',
                steps: [
                    {
                        id: 'proactive-basic',
                        name: '基础设置',
                        icon: '🗣️',
                        desc: '主动对话总开关、沉默阈值、基础触发概率',
                        toggle: 'enable_proactive_chat',
                        keys: ['enable_proactive_chat', 'proactive_silence_threshold',
                               'proactive_probability', 'proactive_check_interval',
                               'proactive_enabled_groups'],
                        onFail: 'drop',
                        failLabel: '未启用 → 不触发',
                        next: 'proactive-activity'
                    },
                    {
                        id: 'proactive-activity',
                        name: '用户活跃检测',
                        icon: '👥',
                        desc: '需要群内有用户近期活跃才触发',
                        parentToggle: 'enable_proactive_chat',
                        keys: ['proactive_require_user_activity',
                               'proactive_min_user_messages',
                               'proactive_user_activity_window'],
                        onFail: 'drop',
                        failLabel: '无活跃用户 → 不触发',
                        next: 'proactive-quiet'
                    },
                    {
                        id: 'proactive-quiet',
                        name: '禁用时段',
                        icon: '🌙',
                        desc: '深夜等时段禁止主动对话',
                        toggle: 'proactive_enable_quiet_time',
                        parentToggle: 'enable_proactive_chat',
                        keys: ['proactive_enable_quiet_time', 'proactive_quiet_start',
                               'proactive_quiet_end', 'proactive_transition_minutes'],
                        onFail: 'drop',
                        failLabel: '禁用时段 → 不触发',
                        next: null
                    }
                ]
            },
            {
                id: 'proactive-decide',
                name: '概率与决策',
                icon: '🎯',
                desc: 'AI预判断 + 概率计算 + 注意力参考，决定是否发起对话',
                nextStage: 'proactive-generate',
                nextLabel: '决定发起对话',
                steps: [
                    {
                        id: 'proactive-ai-judge',
                        name: 'AI预判断',
                        icon: '🤔',
                        desc: '先让AI判断当前是否适合主动发话',
                        toggle: 'enable_proactive_ai_judge',
                        parentToggle: 'enable_proactive_chat',
                        keys: ['enable_proactive_ai_judge',
                               'proactive_ai_judge_prompt',
                               'proactive_ai_judge_timeout'],
                        onFail: 'drop',
                        failLabel: 'AI判定不适合 → 跳过',
                        next: 'proactive-attention'
                    },
                    {
                        id: 'proactive-attention',
                        name: '注意力集成',
                        icon: '🎯',
                        desc: '参考注意力排行榜选择话题对象',
                        toggle: 'proactive_use_attention',
                        parentToggle: 'enable_proactive_chat',
                        keys: ['proactive_use_attention',
                               'proactive_attention_reference_probability',
                               'proactive_attention_rank_weights',
                               'proactive_attention_max_selected_users',
                               'proactive_focus_last_user_probability'],
                        onFail: 'pass',
                        next: 'proactive-time'
                    },
                    {
                        id: 'proactive-time',
                        name: '时间段调整',
                        icon: '🕐',
                        desc: '按时间段调整主动对话概率',
                        toggle: 'enable_dynamic_proactive_probability',
                        parentToggle: 'enable_proactive_chat',
                        keys: ['enable_dynamic_proactive_probability',
                               'proactive_time_periods',
                               'proactive_time_transition_minutes',
                               'proactive_time_min_factor',
                               'proactive_time_max_factor',
                               'proactive_time_use_smooth_curve'],
                        onFail: 'pass',
                        next: 'proactive-failure'
                    },
                    {
                        id: 'proactive-failure',
                        name: '失败冷却',
                        icon: '⏸️',
                        desc: '连续失败后进入冷却期，降低触发频率',
                        parentToggle: 'enable_proactive_chat',
                        keys: ['proactive_max_consecutive_failures',
                               'proactive_failure_sequence_probability',
                               'proactive_failure_threshold_perturbation',
                               'proactive_cooldown_duration'],
                        onFail: 'drop',
                        failLabel: '冷却中 → 跳过',
                        next: null
                    }
                ]
            },
            {
                id: 'proactive-generate',
                name: '生成与反馈',
                icon: '✨',
                desc: 'AI生成主动话题，发送后收集反馈调整后续策略',
                nextStage: null,
                nextLabel: null,
                steps: [
                    {
                        id: 'proactive-gen',
                        name: 'AI话题生成',
                        icon: '💬',
                        desc: '调用AI生成主动对话内容，支持重试和@转换',
                        promptDataKey: 'proactive-ai',
                        parentToggle: 'enable_proactive_chat',
                        keys: ['proactive_prompt', 'proactive_retry_prompt',
                               'proactive_generation_timeout_warning',
                               'proactive_reply_context_prompt',
                               'enable_proactive_at_conversion'],
                        onFail: 'pass',
                        next: 'proactive-boost'
                    },
                    {
                        id: 'proactive-boost',
                        name: '临时概率提升',
                        icon: '⚡',
                        desc: '主动发言后短暂提升回复概率，延续对话',
                        parentToggle: 'enable_proactive_chat',
                        keys: ['proactive_temp_boost_probability',
                               'proactive_temp_boost_duration'],
                        onFail: 'pass',
                        next: 'adaptive'
                    },
                    {
                        id: 'adaptive',
                        name: '自适应系统',
                        icon: '📈',
                        desc: '根据用户互动反馈自动调整主动对话频率',
                        toggle: 'enable_adaptive_proactive',
                        parentToggle: 'enable_proactive_chat',
                        keys: ['enable_adaptive_proactive',
                               'score_increase_on_success', 'score_decrease_on_fail',
                               'score_quick_reply_bonus', 'score_multi_user_bonus',
                               'score_streak_bonus', 'score_revival_bonus',
                               'interaction_score_decay_rate',
                               'interaction_score_min', 'interaction_score_max'],
                        onFail: 'pass',
                        next: 'complaint'
                    },
                    {
                        id: 'complaint',
                        name: '吐槽系统',
                        icon: '😤',
                        desc: '多次主动对话无人回复时，触发幽默吐槽',
                        toggle: 'enable_complaint_system',
                        parentToggle: 'enable_proactive_chat',
                        keys: ['enable_complaint_system', 'complaint_trigger_threshold',
                               'complaint_level_light', 'complaint_probability_light',
                               'complaint_level_medium', 'complaint_probability_medium',
                               'complaint_level_strong', 'complaint_probability_strong',
                               'complaint_decay_on_success',
                               'complaint_decay_check_interval',
                               'complaint_decay_no_failure_threshold',
                               'complaint_decay_amount',
                               'complaint_max_accumulation'],
                        onFail: 'pass',
                        next: null
                    }
                ]
            }
        ];
    },

    // ==================== 私信流水线 ====================

    _privateStages() {
        return [
            {
                id: 'private-entry',
                name: '私信处理',
                icon: '📱',
                desc: '⚠️ 此功能目前未开放',
                nextStage: null,
                nextLabel: null,
                steps: [
                    {
                        id: 'private-basic',
                        name: '私信基础',
                        icon: '📱',
                        desc: '⚠️ 此功能目前未开放',
                        toggle: 'enable_private_chat',
                        disabled: true,
                        keys: ['enable_private_chat'],
                        onFail: 'pass',
                        next: 'private-filter'
                    },
                    {
                        id: 'private-filter',
                        name: '用户过滤',
                        icon: '🔘',
                        desc: '私信用户黑白名单',
                        parentToggle: 'enable_private_chat',
                        disabled: true,
                        keys: ['private_enable_user_filter',
                               'private_user_filter_mode',
                               'private_user_filter_list'],
                        onFail: 'pass',
                        next: 'private-aggregator'
                    },
                    {
                        id: 'private-aggregator',
                        name: '消息聚合',
                        icon: '📦',
                        desc: '连续消息合并处理',
                        parentToggle: 'enable_private_chat',
                        disabled: true,
                        keys: ['private_enable_message_aggregator',
                               'private_aggregator_wait_time',
                               'private_aggregator_max_messages',
                               'private_aggregator_separator',
                               'private_enable_aggregator_filter',
                               'private_aggregator_filter_mode',
                               'private_aggregator_filter_list'],
                        onFail: 'pass',
                        next: 'private-message'
                    },
                    {
                        id: 'private-message',
                        name: '消息处理',
                        icon: '📝',
                        desc: '时间戳、发送者信息',
                        parentToggle: 'enable_private_chat',
                        disabled: true,
                        keys: ['private_include_timestamp',
                               'private_include_sender_info'],
                        onFail: 'pass',
                        next: 'private-image'
                    },
                    {
                        id: 'private-image',
                        name: '图片处理',
                        icon: '🖼️',
                        desc: '私信图片转文字与缓存',
                        parentToggle: 'enable_private_chat',
                        disabled: true,
                        keys: ['private_enable_image_processing',
                               'private_image_to_text_provider_id',
                               'private_image_to_text_prompt',
                               'private_image_to_text_timeout',
                               'private_max_images_per_message',
                               'private_enable_image_description_cache',
                               'private_image_description_cache_max_entries',
                               'private_gcp_clear_image_cache_filter_mode',
                               'private_gcp_clear_image_cache_filter_list'],
                        onFail: 'pass',
                        next: 'private-command'
                    },
                    {
                        id: 'private-command',
                        name: '指令过滤',
                        icon: '⌨️',
                        desc: '私信指令前缀过滤',
                        parentToggle: 'enable_private_chat',
                        disabled: true,
                        keys: ['private_enable_command_filter',
                               'private_command_prefixes',
                               'private_enable_full_command_detection',
                               'private_full_command_list',
                               'private_enable_command_prefix_match',
                               'private_command_prefix_match_list'],
                        onFail: 'pass',
                        next: 'private-debug'
                    },
                    {
                        id: 'private-debug',
                        name: '调试设置',
                        icon: '🔍',
                        desc: '私信处理详细日志',
                        parentToggle: 'enable_private_chat',
                        disabled: true,
                        keys: ['private_chat_enable_debug_log'],
                        onFail: 'pass',
                        next: null
                    }
                ]
            }
        ];
    },

    // ==================== 查询方法（兼容 ConfigEditor） ====================

    /** 根据 ID 获取步骤（节点）数据 */
    getNodeById(id) {
        return this._nodeMap[id] || null;
    },

    /** 根据 ID 获取阶段 */
    getStageById(id) {
        return this._stageMap[id] || null;
    },

    /** 根据 ID 获取流水线 */
    getPipelineById(id) {
        return this.pipelines.find(p => p.id === id) || null;
    },

    /** 获取步骤所属的阶段和流水线 */
    getStepContext(stepId) {
        for (const pipeline of this.pipelines) {
            for (const stage of pipeline.stages) {
                for (const step of stage.steps) {
                    if (step.id === stepId) {
                        return { step, stage, pipeline };
                    }
                }
            }
        }
        return null;
    },

    /** 获取所有步骤的扁平列表（兼容旧 getAllNodes） */
    getAllNodes() {
        const all = [];
        for (const pipeline of this.pipelines) {
            for (const stage of pipeline.stages) {
                for (const step of stage.steps) {
                    all.push({ ...step, stageId: stage.id, pipelineId: pipeline.id });
                }
            }
        }
        return all;
    },

    /** 根据配置key查找所属步骤（兼容旧 findNodeByKey） */
    findNodeByKey(key) {
        for (const pipeline of this.pipelines) {
            for (const stage of pipeline.stages) {
                for (const step of stage.steps) {
                    if (step.keys && step.keys.includes(key)) {
                        return { node: step, flow: { id: pipeline.id, name: pipeline.name } };
                    }
                }
            }
        }
        return null;
    }
};

// 初始化
FlowData.init();
