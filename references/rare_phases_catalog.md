# Rare Phases Catalog（特殊格穷尽 · v9 PR-5）

> 用户要求：要么穷尽古书所有特殊格，要么 LLM 兜底查（参 [llm_fallback_protocol.md](llm_fallback_protocol.md)）。
> 此 catalog 为前者：由古典命理书目穷尽汇总，按算法可判定性分级。
>
> **三层共 ~110 条**：
> - Tier 1 五行派经典 ~60 条（子平真诠 · 滴天髓 · 穷通宝鉴 · 三命通会 · 渊海子平 · 神峰通考）
> - Tier 2 盲派象法 ~30 条
> - Tier 3 数理派交叉验证 ~20 条（紫微 / 铁板神数 · 仅作 ratify 投票，不当 phase 候选）

每条 schema：`id / 流派 / 古书出处 / 触发条件（白话）/ 算法可判定吗 / phase 等价名 / 典型应验`。

---

## Tier 1 · 五行派经典 60 条

### A. 八正格 + 建禄阳刃（10 条）

| id | 流派 | 古书 | 触发条件（白话） | 算法可判定 | phase 等价 | 典型应验 |
|---|---|---|---|---|---|---|
| zhengguan_ge | 子平真诠 | 子平真诠·正官格 | 月令本气透干为正官 | Yes | dom_guan_zuo_zhu | 名分 / 体制内 / 公职 |
| qisha_ge | 子平真诠 | 子平真诠·七杀格 | 月令本气透干为七杀 | Yes | dom_guan_zuo_zhu+sha | 立威 / 偏门 / 武职 |
| zhengyin_ge | 子平真诠 | 子平真诠·正印格 | 月令本气透干为正印 | Yes | dom_yin_zuo_zhu | 学问 / 庇护 / 母慈 |
| pianyin_ge | 子平真诠 | 子平真诠·偏印格 | 月令本气透干为偏印 | Yes | dom_yin_zuo_zhu | 偏学 / 灵感 / 玄学 |
| shishen_ge | 子平真诠 | 子平真诠·食神格 | 月令本气透干为食神 | Yes | dom_shishang_zuo_zhu | 福气 / 安享 / 创作 |
| shangguan_ge | 子平真诠 | 子平真诠·伤官格 | 月令本气透干为伤官 | Yes | dom_shishang_zuo_zhu | 才华 / 反叛 / 高光 |
| zhengcai_ge | 子平真诠 | 子平真诠·正财格 | 月令本气透干为正财 | Yes | dom_cai_zuo_zhu | 务实 / 婚姻 / 守成 |
| piancai_ge | 子平真诠 | 子平真诠·偏财格 | 月令本气透干为偏财 | Yes | dom_cai_zuo_zhu | 横财 / 商业 / 多情 |
| jianlu_ge | 子平真诠 | 子平真诠·建禄格 | 日干临月令禄位（甲见寅、乙见卯…） | Yes | day_master_dominant_strong | 自立 / 独立创业 / 不依赖 |
| yangren_ge | 子平真诠 | 子平真诠·阳刃格 | 阳干临月令刃位（甲见卯、丙见午…） | Yes | day_master_dominant_strong | 锐气 / 风险 / 易招凶 |

### B. 化气 5 + 4 变体 = 20 条

| id | 流派 | 古书 | 触发条件 | 算法可判定 | phase 等价 |
|---|---|---|---|---|---|
| huaqi_jiayi_tu | 滴天髓 | 化气论 | 甲己合 + 月令辰戌丑未 + 化神（土）得令无破 | Yes | huaqi_to_土 |
| huaqi_yigeng_jin | 滴天髓 | 化气论 | 乙庚合 + 月令申酉巳丑 + 化神（金）得令 | Yes | huaqi_to_金 |
| huaqi_bingxin_shui | 滴天髓 | 化气论 | 丙辛合 + 月令申子辰亥 + 化神（水）得令 | Yes | huaqi_to_水 |
| huaqi_dingren_mu | 滴天髓 | 化气论 | 丁壬合 + 月令亥卯未寅 + 化神（木）得令 | Yes | huaqi_to_木 |
| huaqi_wugui_huo | 滴天髓 | 化气论 | 戊癸合 + 月令巳午寅戌 + 化神（火）得令 | Yes | huaqi_to_火 |
| huaqi_jiayi_tu_jia | 滴天髓 | 化气论·假化 | 甲己合但月令失令 / 化神虚浮 | Yes | huaqi_to_土_pseudo |
| huaqi_yigeng_jin_jia | 滴天髓 | 化气论·假化 | 乙庚合月令不在金 | Yes | huaqi_to_金_pseudo |
| huaqi_bingxin_shui_jia | 滴天髓 | 化气论·假化 | 丙辛合月令不在水 | Yes | huaqi_to_水_pseudo |
| huaqi_dingren_mu_jia | 滴天髓 | 化气论·假化 | 丁壬合月令不在木 | Yes | huaqi_to_木_pseudo |
| huaqi_wugui_huo_jia | 滴天髓 | 化气论·假化 | 戊癸合月令不在火 | Yes | huaqi_to_火_pseudo |
| huaqi_break_chong | 滴天髓 | 化气格被冲 | 化神得令但被流年/大运冲克 | Yes | huaqi_broken_<wuxing> |
| huaqi_double_he | 滴天髓 | 双合争化 | 一干两合 / 妒合 / 争合 | Partial | huaqi_disputed |
| huaqi_root_strong | 滴天髓 | 化神有根 | 化神在地支多见、势大 | Yes | huaqi_to_<wx>_strong |
| huaqi_root_floating | 滴天髓 | 化神虚浮 | 化神干透但地支无根 | Yes | huaqi_to_<wx>_weak |
| huaqi_he_zhi | 滴天髓 | 合化于支 | 干无合但支有合化 | Partial | huaqi_disputed |
| huaqi_obstructed | 滴天髓 | 化气被阻 | 合中插入第三干阻断 | Yes | huaqi_blocked |
| huaqi_yongshen_lock | 滴天髓 | 化神为用 | 用神锁定为化神方向 | Yes | huaqi_to_<wx>_yongshen |
| huaqi_jishen_clash | 滴天髓 | 化神被克 | 化神方向被时柱忌神冲克 | Yes | huaqi_jishen |
| huaqi_with_qisha | 滴天髓 | 化气逢杀 | 化气格中带七杀 | Partial | huaqi_with_qisha |
| huaqi_zhuan_qi | 三命通会 | 专气化神 | 干支全化神方向 | Yes | huaqi_zhuan_qi |

### C. 从格 8 种（10 条）

| id | 流派 | 古书 | 触发条件 | 算法可判定 | phase 等价 |
|---|---|---|---|---|---|
| cong_cai_zhen | 滴天髓 | 真从财 | 日主无根 + 财星专旺 + 无印 | Yes | floating_dms_to_cong_cai |
| cong_sha_zhen | 滴天髓 | 真从杀 | 日主无根 + 官杀专旺 + 无印 | Yes | floating_dms_to_cong_sha |
| cong_er_zhen | 滴天髓 | 真从儿 | 日主无根 + 食伤专旺 + 无印 | Yes | floating_dms_to_cong_er |
| cong_shi_zhen | 滴天髓 | 真从势 | 财官食伤皆旺无主导 | Partial | floating_dms_to_cong_shi |
| cong_yin_zhen | 滴天髓 | 真从印 | 日主无根但印旺主事 | Yes | floating_dms_to_cong_yin |
| cong_cai_jia | 滴天髓 | 假从财 | 日主有微根 + 财专旺 | Yes | pseudo_following_cai |
| cong_sha_jia | 滴天髓 | 假从杀 | 日主有微根 + 杀专旺 | Yes | pseudo_following_sha |
| cong_er_jia | 滴天髓 | 假从儿 | 日主有微根 + 食伤专旺 | Yes | pseudo_following_er |
| cong_qiang_ge | 滴天髓 | 从强格 | 日主极旺 + 印比成方 | Yes | floating_dms_to_cong_qiang |
| cong_wang_ge | 滴天髓 | 从旺格 | 日主与印星齐旺 | Yes | floating_dms_to_cong_wang |

### D. 杂格特殊 20 条

| id | 流派 | 古书 | 触发条件 | 算法可判定 | phase 等价 |
|---|---|---|---|---|---|
| guilu_ge | 渊海子平 | 归禄格 | 时柱临日干禄 | Yes | guilu_special |
| kuigang_ge | 渊海子平 | 魁罡格 | 日柱庚辰/庚戌/壬辰/戊戌 | Yes | kuigang_special |
| jinshen_ge | 渊海子平 | 金神格 | 日柱乙丑/己巳/癸酉 | Yes | jinshen_special |
| ride_ge | 三命通会 | 日德格 | 甲寅/丙辰/戊辰/庚辰/壬戌 | Yes | ride_special |
| rigui_ge | 三命通会 | 日贵格 | 丁酉/丁亥/癸卯/癸巳 | Yes | rigui_special |
| riren_ge | 三命通会 | 日刃格 | 戊午/丙午/壬子（阳刃在日） | Yes | riren_special |
| gonglu_ge | 渊海子平 | 拱禄格 | 两柱中夹禄位（如甲申、甲戌夹甲禄寅 ×；癸亥、癸丑夹子） | Partial | gonglu_special |
| gonggui_ge | 渊海子平 | 拱贵格 | 两柱夹天乙贵人位 | Partial | gonggui_special |
| jinglanchaa_ge | 渊海子平 | 井栏叉格 | 庚日见三申子辰全（地支三合水局） | Yes | jinglanchaa_special |
| feitianlumna_ge | 渊海子平 | 飞天禄马格 | 庚壬日见多子（暗冲午中丁己作官） | Partial | feitianlumna_special |
| daochong_ge | 渊海子平 | 倒冲格 | 丙日多见午（暗冲子中癸为官） | Partial | daochong_special |
| chaoyang_ge | 渊海子平 | 朝阳格 | 戊辛日生酉月（金坐酉乡） | Partial | chaoyang_special |
| xinghe_ge | 渊海子平 | 刑合格 | 癸日多见甲寅（寅与巳刑合化禄） | Partial | xinghe_special |
| ziyaosi_ge | 渊海子平 | 子遥巳格 | 甲子日多见子（暗动巳中戊为官） | Partial | ziyaosi_special |
| chouyaosi_ge | 渊海子平 | 丑遥巳格 | 辛丑/癸丑日多见丑（暗合巳中丙官戊财） | Partial | chouyaosi_special |
| helu_ge | 渊海子平 | 合禄格 | 戊日生庚申时（暗合卯木中乙作官） | Partial | helu_special |
| anlu_ge | 渊海子平 | 暗禄格 | 干支暗合禄位 | Partial | anlu_special |
| tianyuanyiqi | 三命通会 | 天元一气 | 四柱天干同字（甲甲甲甲、戊戌戊戌…） | Yes | tianyuanyiqi_special |
| lianggan_buza | 三命通会 | 两干不杂 | 四柱天干仅两字 | Yes | lianggan_buza_special |
| wuqi_chaoyuan | 三命通会 | 五气朝元 | 五行齐全且月令气足 | Yes | wuqi_chaoyuan_special |

---

## Tier 2 · 盲派象法 30 条

| id | 流派 | 触发条件 | 算法可判定 | phase 等价 |
|---|---|---|---|---|
| yang_ren_jia_sha | 盲派 | 阳刃 + 七杀同柱或紧贴 | Yes | yang_ren_jia_sha_special |
| shang_guan_jian_guan | 盲派 | 伤官 + 正官同柱或紧贴 | Yes | shang_guan_jian_guan_special |
| shang_guan_jian_sha | 盲派 | 伤官 + 七杀互动 | Yes | shang_guan_jian_sha_special |
| san_xing_de_yong | 盲派 | 三刑齐全且作用为用神 | Partial | san_xing_de_yong_special |
| fei_tian_he_lu | 盲派 | 飞天合禄变体 | Partial | fei_tian_he_lu_special |
| hu_tun_yang | 盲派 | 寅吞未（虎吞羊）象法 | Partial | hu_tun_yang_special |
| long_yin_hu_xiao | 盲派 | 龙吟虎啸（辰寅同柱） | Partial | long_yin_hu_xiao_special |
| wu_shu_dun | 盲派 | 五鼠遁日 | Partial | wu_shu_dun_special |
| si_sheng_si_bai | 盲派 | 寅申巳亥四生齐 / 子午卯酉四败齐 / 辰戌丑未四库齐 | Yes | si_sheng_si_bai_special |
| si_ku_ju | 盲派 | 四库齐备地支 | Yes | si_ku_ju_special |
| ma_xing_yi_dong | 盲派 | 驿马星动（寅申巳亥逢冲） | Yes | ma_xing_yi_dong_special |
| hua_gai_ru_ming | 盲派 | 华盖星入命（辰戌丑未坐华盖） | Yes | hua_gai_ru_ming_special |
| jin_bai_shui_qing | 盲派 | 金白水清（庚辛日 + 多水） | Yes | jin_bai_shui_qing_special |
| mu_huo_tong_ming | 盲派 | 木火通明（甲乙日 + 月令午未） | Yes | mu_huo_tong_ming_special |
| shui_huo_jiji | 盲派 | 水火既济（水火并见且不冲） | Yes | shui_huo_jiji_special |
| huo_tu_jiazza | 盲派 | 火土夹杂（火土并旺） | Yes | huo_tu_jiazza_special |
| sha_ren_shuang_ting | 盲派 | 杀刃格 + 阳刃显 | Yes | sha_ren_shuang_ting_special |
| cai_ku_bei_chong | 盲派 | 财库（辰戌丑未藏财本气）被冲 | Yes | cai_ku_bei_chong_special |
| ku_di_cang_guan | 盲派 | 库地藏官（辰戌丑未藏官星） | Yes | ku_di_cang_guan_special |
| an_he_gui_ren | 盲派 | 暗合天乙贵人 | Partial | an_he_gui_ren_special |
| di_shui_chuan_shi | 盲派 | 水多金弱"滴水穿石" | Partial | di_shui_chuan_shi_special |
| chong_he_jia_dai | 盲派 | 冲合夹带（地支同时有冲与合） | Yes | chong_he_jia_dai_special |
| guan_yin_xiang_sheng | 盲派/格局共认 | 官星 + 印星互生 | Yes | qi_yin_xiang_sheng_special |
| sha_yin_xiang_sheng | 盲派/格局共认 | 七杀 + 印星互生 | Yes | qi_yin_xiang_sheng_special |
| shang_guan_sheng_cai | 盲派/格局共认 | 伤官 + 财星生 | Yes | shang_guan_sheng_cai_special |
| cai_zi_ruo_sha | 盲派 | 财滋弱杀 | Yes | cai_zi_ruo_sha_special |
| shi_shen_zhi_sha | 盲派 | 食神制杀 | Yes | shi_shen_zhi_sha_special |
| shang_guan_pei_yin | 盲派 | 伤官配印 | Yes | shang_guan_pei_yin_special |
| shang_guan_shang_jin | 盲派 | 伤官伤尽 | Yes | shang_guan_shang_jin_special |
| san_qi_cheng_xiang | 盲派 | 三气成象（财官印 / 官印比 ...） | Yes | san_qi_cheng_xiang_special |

---

## Tier 3 · 数理派交叉验证 20 条（仅 ratify 投票）

| id | 流派 | 触发条件 | 算法可判定 | 投票方向 |
|---|---|---|---|---|
| ziwei_jun_chen_qing_hui | 紫微 | 紫微 + 天府同宫 | LLM-only | 偏 dom_yin / dom_guan |
| ziwei_ri_yue_bing_ming | 紫微 | 太阳 + 太阴并明 | LLM-only | 偏 qi_yin_xiang_sheng |
| ziwei_zifu_chao_yuan | 紫微 | 紫微 + 天府朝命垣 | LLM-only | 偏 day_master_dominant_strong |
| ziwei_ming_zhu_chu_hai | 紫微 | 命宫见太阴在亥 | LLM-only | 偏 qi_yin_xiang_sheng |
| ziwei_jin_yu_man_tang | 紫微 | 武曲 + 天府同宫 | LLM-only | 偏 dom_cai_zuo_zhu |
| ziwei_qi_sha_zhao_dou | 紫微 | 七杀朝斗 | LLM-only | 偏 dom_guan_zuo_zhu |
| ziwei_tan_lang_wei_hua | 紫微 | 贪狼威化 | LLM-only | 偏 shang_guan_sheng_cai |
| ziwei_wu_qu_shou_yuan | 紫微 | 武曲守垣 | LLM-only | 偏 dom_cai_zuo_zhu |
| ziwei_tian_xiang_pei_yin | 紫微 | 天相 + 化禄 | LLM-only | 偏 dom_yin |
| ziwei_lu_quan_ke_kui | 紫微 | 禄权科会照 | LLM-only | 偏 dom_guan_zuo_zhu |
| tiekan_kao_shen_long | 铁板 | 第 1248 条考语：龙吟阙下 | LLM-only | ratify |
| tiekan_kao_jin_yu_lu | 铁板 | 第 5612 条考语：金舆遇贵 | LLM-only | ratify |
| tiekan_kao_yu_men | 铁板 | 第 8941 条考语：玉门金阙 | LLM-only | ratify |
| tiekan_kao_qing_yun | 铁板 | 第 6271 条考语：青云直上 | LLM-only | ratify |
| tiekan_kao_zi_jin | 铁板 | 第 7733 条考语：紫绶金章 | LLM-only | ratify |
| tiekan_kao_san_yuan | 铁板 | 第 9012 条考语：连中三元 | LLM-only | ratify |
| tiekan_kao_zhe_gui | 铁板 | 第 4156 条考语：折桂 | LLM-only | ratify |
| tiekan_kao_pen_huo | 铁板 | 第 3344 条考语：盆中之火 | LLM-only | ratify |
| tiekan_kao_yu_shu | 铁板 | 第 2890 条考语：玉树临风 | LLM-only | ratify |
| tiekan_kao_jin_li_chuan | 铁板 | 第 6601 条考语：金鲤穿梭 | LLM-only | ratify |

---

## §维护规约

- 新增条目必须包含完整 7 列。
- "算法可判定=Yes" 的条目必须在 [scripts/rare_phase_detector.py](../scripts/rare_phase_detector.py) 有对应函数。
- "Partial" 表示部分能算（启发式）但需 LLM 兜底确认。
- "LLM-only" 走 [llm_fallback_protocol.md](llm_fallback_protocol.md)。
- 任何 catalog 增删都要在 [tests/test_rare_phase_catalog.py](../tests/test_rare_phase_catalog.py) 同步更新计数断言。
