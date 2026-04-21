from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
import json
import os
import time
from typing import Dict, List

@register("astrbot_plugin_SGDgame", "LZQ123PKQ", "星际黎明 - 太空挂机游戏插件", "1.0.0", "https://github.com/LZQ123PKQ/astrbot_plugin_SGDgame")
class SGDGamePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 使用插件目录下的data文件夹
        self.data_dir = "/root/AstrBot/data/plugin_data/astrbot_plugin_SGDgame"
        os.makedirs(self.data_dir, exist_ok=True)
        self.players_file = os.path.join(self.data_dir, "players.json")
        self.players = self.load_players()
    
    def load_players(self) -> Dict:
        """加载玩家数据"""
        if os.path.exists(self.players_file):
            with open(self.players_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save_players(self):
        """保存玩家数据"""
        with open(self.players_file, 'w', encoding='utf-8') as f:
            json.dump(self.players, f, ensure_ascii=False, indent=2)
    
    def get_player(self, user_id: str) -> Dict:
        """获取玩家数据，实时从文件加载"""
        # 先重新加载文件，确保数据最新
        self.players = self.load_players()
        
        if user_id not in self.players:
            self.players[user_id] = {
                "wallet": 0,  # 初始资金
                "skills": {
                    "采矿护卫舰操控理论": 1  # 初始技能：可驾驶采矿护卫舰
                },
                "skill_progress": {},  # 各技能学习进度（技能名 -> 当前累积技能点）
                "clones": [{"id": 1, "name": "克隆体#001", "status": "待机", "ship_id": None, "location": "地球"}],
                "max_clones": 1,  # 最大克隆体数量
                "assets": {
                    "地球": {"minerals": {}, "ships": [{"id": 1, "name": "蜜蜂级采矿护卫舰", "hp_percent": 100}]}
                },
                "next_ship_id": 2,  # 下一个舰船ID
                "mining": None,  # 当前挖矿状态
                "manufacturing": None,  # 当前制造状态
                "learning": None,  # 当前学习状态
                "combat": None,  # 当前刷怪状态
            }
            self.save_players()
        return self.players[user_id]

    @filter.command("游戏帮助")
    async def game_help(self, event: AstrMessageEvent):
        """显示游戏帮助"""
        help_text = """🚀 星际黎明 - 太空挂机游戏

📋 基础指令：
/游戏注册 - 创建游戏角色
/游戏状态 - 查看当前状态
/游戏资产 - 查看所有行星资产
/游戏资产 <行星> - 查看指定行星资产

🚀 移动：
/游戏星图 - 查看太阳系星图和行星距离
/游戏跃迁 <行星> - 所有待机克隆体跃迁到目标行星
/游戏跃迁 <克隆体ID> <行星> - 指定克隆体跃迁
/游戏跃迁 <克隆体ID1>,<克隆体ID2> <行星> - 多个克隆体跃迁
/游戏跃迁状态 - 查看跃迁进度和跃迁中的克隆体

⛏️ 挖矿：
/游戏挖矿 - 所有待机且有采矿船的克隆体在当前行星挖矿
/游戏挖矿 <克隆体ID1>,<克隆体ID2> - 指定克隆体在当前行星挖矿
/游戏停止挖矿 - 停止挖矿
💡 提示：需要先跃迁到目标行星才能在该行星挖矿

⚔️ 战斗：
/游戏刷怪 <等级> - 开始刷怪(1-6级)
/游戏停止刷怪 - 停止刷怪

🔧 制造：
/游戏制造 <舰船> [数量] - 制造舰船
/游戏制造状态 - 查看制造进度

📚 技能：
/游戏技能 - 查看技能列表（显示ID、等级、技能点进度）
/游戏学习 <技能ID> - 学习技能（可切换不同技能，进度保留）

🚀 舰船：
/游戏舰船 - 查看可用舰船
/游戏机库 - 查看当前行星机库舰船
/游戏机库 <行星> - 查看指定行星机库舰船
/游戏换船 <舰船ID> - 该行星所有待机克隆体换装
/游戏换船 <克隆体ID1>,<克隆体ID2> <舰船ID> - 指定克隆体换装
/游戏换船 <克隆体ID> <舰船ID> - 单个克隆体换装
/游戏离舰 <克隆体ID> - 指定克隆体离舰
/游戏维修 - 维修受损舰船

🚛 运输：
/游戏装载 <舰船ID> <矿物名:吨数,矿物名:吨数...> - 批量装载（不输入数量=全部）
/游戏装载 <舰船ID> <矿物名,矿物名...> - 装载全部该矿物（自动处理超载）
/游戏卸载 <舰船ID> <矿物名:吨数,矿物名:吨数...> - 批量卸载（不输入数量=全部）
/游戏卸载 <舰船ID> <矿物名,矿物名...> - 卸载全部该矿物
💡 提示：货运管理技能每级+10%货仓容量，超载时自动按空间装载

输入 /游戏注册 开始游戏！"""
        yield event.plain_result(help_text)

    @filter.command("游戏注册")
    async def register_player(self, event: AstrMessageEvent):
        """注册新玩家"""
        user_id = str(event.get_sender_id())
        user_name = event.get_sender_name()
        
        if user_id in self.players:
            yield event.plain_result(f"👋 欢迎回来，指挥官 {user_name}！\n输入 /游戏状态 查看当前状态")
            return
        
        player = self.get_player(user_id)
        yield event.plain_result(f"🎉 欢迎加入星际黎明，指挥官 {user_name}！\n\n💰 初始资金：¥0\n📍 出生点：地球\n🚀 初始舰船：蜜蜂级采矿护卫舰\n\n输入 /游戏帮助 查看所有指令")

    @filter.command("游戏注销")
    async def unregister_player(self, event: AstrMessageEvent):
        """注销玩家账号"""
        user_id = str(event.get_sender_id())
        user_name = event.get_sender_name()
        
        if user_id not in self.players:
            yield event.plain_result("❌ 您还没有注册游戏账号")
            return
        
        # 删除玩家数据
        del self.players[user_id]
        self.save_players()
        
        yield event.plain_result(f"⚠️ 指挥官 {user_name}，您的账号已注销\n所有游戏数据已清除\n\n输入 /游戏注册 可以重新创建账号")

    @filter.command("游戏状态")
    async def player_status(self, event: AstrMessageEvent):
        """查看玩家状态 - 自动检查技能升级"""
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        # 只结算跃迁（跃迁完成后需要更新位置和状态）
        # 挖矿、战斗、制造不应该在这里结算，它们需要手动停止
        self.settle_warp(player)
        
        # 检查所有已学习技能的升级情况
        upgrade_messages = []
        skills = player.get('skills', {})
        for skill_name in list(skills.keys()):
            result = self.check_skill_upgrade(player, skill_name)
            if result:
                upgrade_messages.append(result)
        
        # 检查正在学习的技能是否升级
        if player.get('learning'):
            result = self.check_skill_upgrade(player, player['learning']['skill'])
            if result:
                upgrade_messages.append(result)
        
        status_text = f"""📊 指挥官状态

👥 克隆体：{len(player['clones'])}/{player['max_clones']}个"""
        
        # 显示技能升级信息
        if upgrade_messages:
            status_text += "\n\n" + "\n".join(upgrade_messages)
        
        status_text += "\n\n🚀 克隆体状态："
        
        for clone in player['clones']:
            ship = self.get_clone_ship(player, clone)
            ship_name = ship['name'] if ship else "无"
            status_text += f"\n  {clone['name']} - {clone['status']}\n    舰船：{ship_name}\n    位置：{clone['location']}"
        
        # 显示进行中的活动（不包括挖矿，因为克隆体状态已显示）
        if player['combat']:
            status_text += f"\n\n⚔️ 战斗中..."
        if player['learning']:
            learning = player['learning']
            skill_name = learning['skill']
            current_level = learning['current_level']
            current_sp = self.get_current_sp(player, skill_name)
            required_sp = self.get_sp_required(current_level)
            status_text += f"\n\n📚 学习中：{skill_name} [Lv.{current_level}] {current_sp}/{required_sp}"
        if player['manufacturing']:
            status_text += f"\n\n🔧 制造中：{player['manufacturing']['ship']}"
        if player.get('warping'):
            warping = player['warping']
            status_text += f"\n\n🚀 跃迁中...\n  {warping['source']} → {warping['target']}"
        
        yield event.plain_result(status_text)

    # ========== 挖矿系统 ==========
    
    def get_mining_speed(self, ship_name: str, player: Dict) -> float:
        """计算挖矿速度"""
        base_speed = 1 if ship_name == "蜜蜂级采矿护卫舰" else 5  # m³/秒
        skill_bonus = 1 + player['skills'].get('采矿技术', 0) * 0.1
        return base_speed * skill_bonus

    @filter.command("游戏挖矿")
    async def start_mining(self, event: AstrMessageEvent):
        """开始挖矿 - 只能在克隆体当前所在星系挖矿"""
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        args = event.message_str.split()[1:]
        
        # 解析参数（只解析克隆体ID，不解析行星）
        clone_ids = []
        
        if len(args) == 0:
            # 无参数：所有待机且有采矿船的克隆体挖矿
            pass
        elif len(args) >= 1:
            # 参数：克隆体ID列表
            if ',' in args[0]:
                # 克隆体ID列表，如 "1,2,3"
                try:
                    clone_ids = [int(x.strip()) for x in args[0].split(',')]
                except ValueError:
                    yield event.plain_result("❌ 克隆体ID必须是数字，多个ID用逗号分隔\n用法：/游戏挖矿 [克隆体ID1,克隆体ID2]")
                    return
            else:
                # 单个克隆体ID
                try:
                    clone_ids = [int(args[0])]
                except ValueError:
                    yield event.plain_result(f"❌ 克隆体ID必须是数字\n用法：/游戏挖矿 [克隆体ID1,克隆体ID2]")
                    return
        
        # 结算之前的挖矿
        self.settle_mining(player)
        
        # 确定要挖矿的克隆体
        mining_ships = ["蜜蜂级采矿护卫舰", "蝗虫级采矿驳船"]
        target_clones = []
        
        if clone_ids:
            # 指定了克隆体ID
            for cid in clone_ids:
                clone = next((c for c in player['clones'] if c['id'] == cid), None)
                if not clone:
                    yield event.plain_result(f"❌ 找不到ID为{cid}的克隆体")
                    return
                if clone['status'] != '待机':
                    yield event.plain_result(f"❌ {clone['name']} 当前状态为{clone['status']}，无法挖矿")
                    return
                ship = self.get_clone_ship(player, clone)
                if not ship or ship['name'] not in mining_ships:
                    yield event.plain_result(f"❌ {clone['name']} 没有驾驶采矿船。可用采矿船：{', '.join(mining_ships)}")
                    return
                target_clones.append((clone, ship))
        else:
            # 未指定克隆体：找所有待机且有采矿船的克隆体
            for clone in player['clones']:
                if clone['status'] == '待机':
                    ship = self.get_clone_ship(player, clone)
                    if ship and ship['name'] in mining_ships:
                        target_clones.append((clone, ship))
        
        if not target_clones:
            yield event.plain_result("❌ 没有符合条件的克隆体（需要待机状态且驾驶采矿船）")
            return
        
        # 检查是否在同一行星
        locations = set(c['location'] for c, _ in target_clones)
        if len(locations) > 1:
            loc_str = ", ".join(locations)
            yield event.plain_result(f"❌ 指定克隆体不在同一行星（当前位置：{loc_str}）\n请先使用 /游戏跃迁 让所有克隆体到同一行星")
            return
        
        planet = target_clones[0][0]['location']
        
        # 开始挖矿
        total_speed = 0
        clone_infos = []
        speed_per_clone = {}  # 记录每个克隆体的挖矿速度
        
        for clone, ship in target_clones:
            speed = self.get_mining_speed(ship['name'], player)
            total_speed += speed
            speed_per_clone[clone['id']] = speed
            cargo = self.get_ship_cargo_capacity(ship['name'])
            clone_infos.append(f"{clone['name']}({ship['name']}, 矿舱{cargo}m³)")
            
            # 更新克隆体状态
            clone['status'] = '挖矿中'
            clone['location'] = f"{planet}小行星带"
        
        player['mining'] = {
            "start_time": time.time(),
            "planet": planet,
            "total_speed": total_speed,
            "speed_per_clone": speed_per_clone,  # 每个克隆体的速度
            "clone_ids": [c['id'] for c, _ in target_clones]
        }
        self.save_players()
        
        clone_text = "\n".join(clone_infos)
        yield event.plain_result(f"⛏️ 开始挖矿\n📍 地点：{planet}小行星带\n👥 挖矿克隆体：\n{clone_text}\n⚡ 总速度：{total_speed:.1f}m³/秒\n\n使用 /游戏停止挖矿 结束挖矿并结算")

    @filter.command("游戏停止挖矿")
    async def stop_mining(self, event: AstrMessageEvent):
        """停止挖矿"""
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        if not player['mining']:
            yield event.plain_result("❌ 当前没有进行挖矿")
            return
        
        result = self.settle_mining(player)
        self.save_players()
        yield event.plain_result(result)

    def calculate_mining_progress(self, player: Dict, save_to_warehouse: bool = False) -> tuple:
        """计算挖矿进度，可选择是否保存到仓库
        
        Args:
            player: 玩家数据
            save_to_warehouse: 是否将矿物保存到仓库（不停止挖矿）
            
        Returns:
            (result_text, total_tons): 结果文本和总吨数
        """
        if not player['mining']:
            return "", 0
        
        mining = player['mining']
        duration = time.time() - mining['start_time']
        
        # 安全区矿物比例
        minerals_ratio = {
            "硫": 0.50, "铁": 0.20, "镁": 0.10, "硅": 0.08,
            "铝": 0.06, "锰": 0.04, "锌": 0.02
        }
        
        # 体积(m³/吨)
        mineral_volume = {
            "硫": 0.483, "铁": 0.127, "镁": 0.575, "硅": 0.429,
            "铝": 0.370, "锰": 0.137, "锌": 0.140
        }
        
        planet = mining['planet']
        if planet not in player['assets']:
            player['assets'][planet] = {"minerals": {}, "ships": []}
        
        # 计算每个克隆体的挖矿情况
        result_text = f"⛏️ 挖矿进度\n📍 地点：{planet}\n\n"
        total_all_tons = 0
        unload_count = 0
        
        for clone_id in mining['clone_ids']:
            clone = next((c for c in player['clones'] if c['id'] == clone_id), None)
            if not clone:
                continue
            
            ship = self.get_clone_ship(player, clone)
            if not ship:
                continue
            
            ship_name = ship['name']
            cargo_capacity = self.get_ship_cargo_capacity(ship_name)
            mining_speed = mining['speed_per_clone'].get(clone_id, 1)
            
            # 计算该克隆体挖了多少体积
            volume_mined = mining_speed * duration
            
            # 检查矿舱是否满了（需要卸货）
            unload_cycles = 0
            actual_volume = 0
            remaining_volume = volume_mined
            
            while remaining_volume > 0:
                if remaining_volume <= cargo_capacity:
                    # 最后一次，不需要卸货
                    actual_volume += remaining_volume
                    remaining_volume = 0
                else:
                    # 矿舱满了，卸货后继续挖
                    actual_volume += cargo_capacity
                    remaining_volume -= cargo_capacity
                    unload_cycles += 1
            
            # 计算获得的矿物
            clone_tons = 0
            for mineral, ratio in minerals_ratio.items():
                tons = (actual_volume * ratio) / mineral_volume[mineral]
                if tons > 0:
                    if save_to_warehouse:
                        # 保存到仓库
                        if mineral not in player['assets'][planet]['minerals']:
                            player['assets'][planet]['minerals'][mineral] = 0
                        player['assets'][planet]['minerals'][mineral] += tons
                    clone_tons += tons
            
            total_all_tons += clone_tons
            unload_count += unload_cycles
            
            # 显示该克隆体的挖矿结果
            unload_info = f" (卸货{unload_cycles}次)" if unload_cycles > 0 else ""
            result_text += f"👤 {clone['name']} ({ship_name})\n"
            result_text += f"   挖取：{clone_tons:.2f}吨{unload_info}\n"
        
        # 计算总卸货时间（每次卸货暂停1分钟）
        total_unload_time = unload_count * 60  # 秒
        actual_mining_time = duration - total_unload_time
        
        result_text += f"\n⏱️ 总时长：{duration/60:.1f}分钟"
        if unload_count > 0:
            result_text += f" (挖矿{actual_mining_time/60:.1f}分钟 + 卸货{unload_count}分钟)"
        result_text += f"\n📊 总计：{total_all_tons:.2f}吨"
        
        return result_text, total_all_tons

    def settle_mining(self, player: Dict) -> str:
        """结算挖矿收益 - 停止挖矿并保存矿物到仓库"""
        if not player['mining']:
            return ""
        
        # 计算并保存到仓库
        result_text, _ = self.calculate_mining_progress(player, save_to_warehouse=True)
        result_text = result_text.replace("⛏️ 挖矿进度", "⛏️ 挖矿结算")
        
        mining = player['mining']
        planet = mining['planet']
        
        # 恢复克隆体状态
        for clone in player['clones']:
            if clone['id'] in mining['clone_ids']:
                clone['status'] = '待机'
                clone['location'] = planet
        
        player['mining'] = None
        return result_text

    def save_mining_progress(self, player: Dict) -> str:
        """保存挖矿进度到仓库 - 不停止挖矿"""
        if not player['mining']:
            return ""
        
        # 计算并保存到仓库，但不停止挖矿
        result_text, _ = self.calculate_mining_progress(player, save_to_warehouse=True)
        
        # 重置挖矿开始时间，以便下次计算增量
        player['mining']['start_time'] = time.time()
        
        return result_text

    # ========== 技能系统 ==========
    
    # 技能ID映射表
    SKILL_LIST = [
        "护卫舰操控理论", "驱逐舰操控理论", "巡洋舰操控理论", "战列舰操控理论",
        "采矿护卫舰操控理论", "采矿驳船操控理论", "运输舰操控理论", "货舰操控理论",
        "护卫舰武器精通", "驱逐舰武器精通", "巡洋舰武器精通", "战列舰武器精通",
        "跃迁引擎操控", "货运管理", "克隆体同步理论", "采矿技术", "批量生产"
    ]
    
    def get_skill_id(self, skill_name: str) -> int:
        """获取技能ID（1-17）"""
        try:
            return self.SKILL_LIST.index(skill_name) + 1
        except ValueError:
            return 0
    
    def get_skill_name(self, skill_id: int) -> str:
        """根据ID获取技能名"""
        if 1 <= skill_id <= len(self.SKILL_LIST):
            return self.SKILL_LIST[skill_id - 1]
        return ""
    
    def get_sp_required(self, level: int) -> int:
        """获取升级所需技能点"""
        if level >= 10:
            return 0
        return 64 * (2 ** level)
    
    def get_current_sp(self, player: Dict, skill_name: str) -> int:
        """获取技能当前累积的技能点"""
        # 从skill_progress中获取已保存的进度
        progress = player.get('skill_progress', {}).get(skill_name, 0)
        
        # 如果正在学习该技能，加上当前学习进度
        if player.get('learning') and player['learning']['skill'] == skill_name:
            learning = player['learning']
            duration = time.time() - learning['start_time']
            progress += int(duration / 60 * 20)
        
        return progress
    
    def check_skill_upgrade(self, player: Dict, skill_name: str) -> str:
        """检查技能是否可以升级，如果可以则自动升级"""
        current_level = player['skills'].get(skill_name, 0)
        if current_level >= 10:
            return ""
        
        current_sp = self.get_current_sp(player, skill_name)
        sp_required = self.get_sp_required(current_level)
        
        if current_sp >= sp_required:
            # 可以升级
            levels_gained = 0
            remaining_sp = current_sp
            
            while remaining_sp >= sp_required and current_level + levels_gained < 10:
                remaining_sp -= sp_required
                levels_gained += 1
                if current_level + levels_gained < 10:
                    sp_required = self.get_sp_required(current_level + levels_gained)
            
            # 应用升级
            new_level = current_level + levels_gained
            player['skills'][skill_name] = new_level
            player['skill_progress'][skill_name] = remaining_sp
            
            # 更新最大克隆体数量
            if skill_name == "克隆体同步理论":
                player['max_clones'] = 1 + new_level
            
            # 如果正在学习该技能，更新学习状态中的当前等级
            if player.get('learning') and player['learning']['skill'] == skill_name:
                player['learning']['current_level'] = new_level
            
            self.save_players()
            return f"🎉 {skill_name} 升级！Lv.{current_level} → Lv.{new_level}"
        return ""
    
    @filter.command("游戏技能")
    async def list_skills(self, event: AstrMessageEvent):
        """查看技能列表 - 显示当前学习进度，自动检查升级"""
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        # 获取玩家当前技能数据
        skills = player.get('skills', {})
        
        # 检查所有已学习技能的升级情况
        upgrade_messages = []
        for skill_name in list(skills.keys()):
            result = self.check_skill_upgrade(player, skill_name)
            if result:
                upgrade_messages.append(result)
        
        # 检查正在学习的技能是否升级
        if player.get('learning'):
            result = self.check_skill_upgrade(player, player['learning']['skill'])
            if result:
                upgrade_messages.append(result)
        
        def format_skill(skill_id, name):
            level = skills.get(name, 0)
            current_sp = self.get_current_sp(player, name)
            required_sp = self.get_sp_required(level)
            
            if level >= 10:
                return f"ID:{skill_id:2d} {name} [Lv.MAX]"
            elif level > 0 or current_sp > 0:
                return f"ID:{skill_id:2d} {name} [Lv.{level}] {current_sp}/{required_sp}"
            else:
                return f"ID:{skill_id:2d} {name} [未学习] 0/{self.get_sp_required(0)}"
        
        # 检查是否有正在学习的技能
        learning_info = ""
        if player.get('learning'):
            learning_skill = player['learning']['skill']
            learning_id = self.get_skill_id(learning_skill)
            learning_level = player['learning']['current_level']
            current_sp = self.get_current_sp(player, learning_skill)
            required_sp = self.get_sp_required(learning_level)
            learning_info = f"\n📖 正在学习：ID:{learning_id} {learning_skill} [Lv.{learning_level}] {current_sp}/{required_sp}\n"
        
        # 显示升级信息
        upgrade_info = ""
        if upgrade_messages:
            upgrade_info = "\n" + "\n".join(upgrade_messages) + "\n"
        
        skills_text = f"""📚 技能系统{upgrade_info}

技能上限：10级 | 学习方式：挂机，每分钟20技能点
当前可控制克隆体：{player.get('max_clones', 1)}个{learning_info}
🚀 飞船操控类（血量+10%/级，1级可驾驶）：
{format_skill(1, '护卫舰操控理论')}
{format_skill(2, '驱逐舰操控理论')}
{format_skill(3, '巡洋舰操控理论')}
{format_skill(4, '战列舰操控理论')}
{format_skill(5, '采矿护卫舰操控理论')}
{format_skill(6, '采矿驳船操控理论')}
{format_skill(7, '运输舰操控理论')}
{format_skill(8, '货舰操控理论')}

⚔️ 武器系统类（DPS+10%/级）：
{format_skill(9, '护卫舰武器精通')}
{format_skill(10, '驱逐舰武器精通')}
{format_skill(11, '巡洋舰武器精通')}
{format_skill(12, '战列舰武器精通')}

🔧 工程系统类：
{format_skill(13, '跃迁引擎操控')}（跃迁速度+10%/级）
{format_skill(14, '货运管理')}（货仓容量+10%/级）

👥 克隆控制类：
{format_skill(15, '克隆体同步理论')}（控制数量+1/级）

⛏️ 采矿制造类：
{format_skill(16, '采矿技术')}（挖矿速度+10%/级）
{format_skill(17, '批量生产')}（制造数量+1/级）

使用 /游戏学习 <技能ID> 切换学习技能（进度保留）"""
        yield event.plain_result(skills_text)
    
    def pause_learning(self, player: Dict) -> str:
        """暂停学习，保存当前进度，返回结算结果"""
        if not player.get('learning'):
            return ""
        
        learning = player['learning']
        duration = time.time() - learning['start_time']
        sp_gained = int(duration / 60 * 20)  # 每分钟20技能点
        
        skill_name = learning['skill']
        current_level = learning['current_level']
        sp_required = self.get_sp_required(current_level)
        
        # 获取之前保存的进度
        if 'skill_progress' not in player:
            player['skill_progress'] = {}
        
        total_sp = player['skill_progress'].get(skill_name, 0) + sp_gained
        
        # 检查是否升级
        levels_gained = 0
        remaining_sp = total_sp
        
        while remaining_sp >= sp_required and current_level + levels_gained < 10:
            remaining_sp -= sp_required
            levels_gained += 1
            if current_level + levels_gained < 10:
                sp_required = self.get_sp_required(current_level + levels_gained)
        
        # 应用升级
        new_level = current_level + levels_gained
        if skill_name not in player['skills']:
            player['skills'][skill_name] = 0
        player['skills'][skill_name] = new_level
        
        # 保存剩余进度
        player['skill_progress'][skill_name] = remaining_sp
        
        # 更新最大克隆体数量
        if skill_name == "克隆体同步理论":
            player['max_clones'] = 1 + player['skills'][skill_name]
        
        # 暂停学习（清空learning，但保留进度）
        player['learning'] = None
        
        # 返回结果
        if levels_gained > 0:
            return f"🎉 {skill_name} 升级！Lv.{current_level} → Lv.{new_level}"
        return ""
    
    @filter.command("游戏学习")
    async def start_learning(self, event: AstrMessageEvent):
        """开始学习技能 - 使用技能ID"""
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        args = event.message_str.split()[1:]
        if len(args) < 1:
            yield event.plain_result("❌ 用法：/游戏学习 <技能ID>\n例如：/游戏学习 5\n使用 /游戏技能 查看技能ID")
            return
        
        try:
            skill_id = int(args[0])
        except ValueError:
            yield event.plain_result("❌ 技能ID必须是数字")
            return
        
        skill_name = self.get_skill_name(skill_id)
        if not skill_name:
            yield event.plain_result(f"❌ 无效技能ID：{skill_id}。ID范围1-{len(self.SKILL_LIST)}")
            return
        
        # 检查是否已经在学习该技能
        if player.get('learning') and player['learning']['skill'] == skill_name:
            current_level = player['skills'].get(skill_name, 0)
            current_sp = self.get_current_sp(player, skill_name)
            required_sp = self.get_sp_required(current_level)
            yield event.plain_result(f"📚 正在学习 {skill_name}\n当前等级：Lv.{current_level}\n当前进度：{current_sp}/{required_sp} 技能点")
            return
        
        # 暂停之前的学习（保存进度，可能升级）
        pause_result = self.pause_learning(player)
        
        # 获取当前实际等级（可能刚刚升级了）
        current_level = player['skills'].get(skill_name, 0)
        if current_level >= 10:
            yield event.plain_result(f"❌ {skill_name} 已满级(Lv.MAX)")
            return
        
        # 开始新技能学习
        player['learning'] = {
            "start_time": time.time(),
            "skill": skill_name,
            "current_level": current_level
        }
        self.save_players()
        
        # 获取当前进度（包含溢出保留的技能点）
        current_sp = player.get('skill_progress', {}).get(skill_name, 0)
        required_sp = self.get_sp_required(current_level)
        
        result_text = f"📚 开始学习 {skill_name}\n"
        result_text += f"当前等级：Lv.{current_level}\n"
        result_text += f"当前进度：{current_sp}/{required_sp} 技能点"
        if pause_result:
            result_text += f"\n\n{pause_result}"
        yield event.plain_result(result_text)

    # ========== 跃迁系统 ==========
    
    # 行星距离表 (AU)
    PLANET_DISTANCES = {
        ("水星", "金星"): 0.33, ("水星", "地球"): 0.61, ("水星", "火星"): 1.13,
        ("水星", "木星"): 4.81, ("水星", "土星"): 9.19, ("水星", "天王星"): 18.83,
        ("水星", "海王星"): 29.66, ("金星", "地球"): 0.28, ("金星", "火星"): 0.80,
        ("金星", "木星"): 4.48, ("金星", "土星"): 8.86, ("金星", "天王星"): 18.50,
        ("金星", "海王星"): 29.33, ("地球", "火星"): 0.52, ("地球", "木星"): 4.20,
        ("地球", "土星"): 8.58, ("地球", "天王星"): 18.22, ("地球", "海王星"): 29.05,
        ("火星", "木星"): 3.68, ("火星", "土星"): 8.06, ("火星", "天王星"): 17.70,
        ("火星", "海王星"): 28.53, ("木星", "土星"): 4.38, ("木星", "天王星"): 14.02,
        ("木星", "海王星"): 24.85, ("土星", "天王星"): 9.64, ("土星", "海王星"): 20.47,
        ("天王星", "海王星"): 10.83
    }
    
    VALID_PLANETS = ["水星", "金星", "地球", "火星", "木星", "土星", "天王星", "海王星"]
    
    SHIP_WARP_SPEEDS = {
        "狂风级护卫舰": 20, "骤雨级驱逐舰": 15, "烈火级巡洋舰": 10, "怒雷级战列舰": 5,
        "蜜蜂级采矿护卫舰": 15, "蝗虫级采矿驳船": 8,
        "崆峒级运输舰": 10, "泰山级货舰": 3
    }
    
    @filter.command("游戏星图")
    async def show_starmap(self, event: AstrMessageEvent):
        """显示星图 - 所有行星及距离"""
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        # 获取玩家当前位置
        current_planet = player['clones'][0]['location'] if player['clones'] else "地球"
        
        starmap_text = f"""🌌 太阳系星图

📍 当前位置：{current_planet}

行星列表（距离太阳）：
"""
        
        # 行星距离太阳（AU）
        sun_distances = {
            "水星": 0.39, "金星": 0.72, "地球": 1.00, "火星": 1.52,
            "木星": 5.20, "土星": 9.58, "天王星": 19.22, "海王星": 30.05
        }
        
        for planet in self.VALID_PLANETS:
            dist = sun_distances[planet]
            marker = " ⭐" if planet == current_planet else ""
            starmap_text += f"  {planet} ({dist} AU){marker}\n"
        
        starmap_text += "\n📏 行星间距离（AU）：\n"
        
        # 显示从当前位置到其他行星的距离
        for planet in self.VALID_PLANETS:
            if planet != current_planet:
                distance = self.PLANET_DISTANCES.get((current_planet, planet)) or self.PLANET_DISTANCES.get((planet, current_planet))
                if distance:
                    starmap_text += f"  {current_planet} → {planet}: {distance:.2f} AU\n"
        
        starmap_text += "\n💡 使用 /游戏跃迁 <行星> 进行跃迁\n💡 使用 /游戏跃迁 <克隆体ID> <行星> 指定克隆体跃迁"
        yield event.plain_result(starmap_text)
    
    @filter.command("游戏跃迁")
    async def warp_to(self, event: AstrMessageEvent):
        """跃迁到目标行星 - 支持指定克隆体"""
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        args = event.message_str.split()[1:]
        if len(args) < 1:
            # 显示待机的克隆体列表
            idle_clones = [c for c in player['clones'] if c['status'] == '待机']
            if not idle_clones:
                yield event.plain_result("❌ 没有待机的克隆体。请先停止其他活动。")
                return
            
            clone_list = []
            for c in idle_clones:
                ship = self.get_clone_ship(player, c)
                ship_info = f"驾驶 {ship['name']}" if ship else "未驾驶舰船"
                clone_list.append(f"ID:{c['id']} {c['name']} - {ship_info} - 在{c['location']}")
            
            yield event.plain_result(f"🚀 待机克隆体列表：\n" + "\n".join(clone_list) + 
                                   "\n\n用法：\n/游戏跃迁 <行星> - 所有待机克隆体跃迁\n/游戏跃迁 <克隆体ID> <行星> - 指定克隆体跃迁\n/游戏跃迁 <克隆体ID1>,<克隆体ID2> <行星> - 多个克隆体跃迁")
            return
        
        # 解析参数
        clone_ids = []
        target_planet = None
        
        if len(args) == 1:
            # 只有一个参数：认为是目标行星
            target_planet = args[0]
        elif len(args) >= 2:
            # 两个参数：克隆体ID + 目标行星
            if ',' in args[0]:
                # 多个克隆体ID
                try:
                    clone_ids = [int(x.strip()) for x in args[0].split(',')]
                except ValueError:
                    yield event.plain_result("❌ 克隆体ID必须是数字，多个ID用逗号分隔")
                    return
            else:
                # 单个克隆体ID
                try:
                    clone_ids = [int(args[0])]
                except ValueError:
                    # 不是数字，认为是行星名（兼容旧格式）
                    target_planet = args[0]
            
            if not target_planet:
                target_planet = args[1]
        
        # 验证目标行星
        if target_planet not in self.VALID_PLANETS:
            yield event.plain_result(f"❌ 无效行星。可选：{', '.join(self.VALID_PLANETS)}")
            return
        
        # 确定要跃迁的克隆体
        target_clones = []
        skipped_clones = []  # 记录被跳过的克隆体
        
        if clone_ids:
            # 指定了克隆体ID
            for cid in clone_ids:
                clone = next((c for c in player['clones'] if c['id'] == cid), None)
                if not clone:
                    yield event.plain_result(f"❌ 找不到ID为{cid}的克隆体")
                    return
                if clone['status'] != '待机':
                    yield event.plain_result(f"❌ {clone['name']} 当前状态为{clone['status']}，无法跃迁")
                    return
                
                # 检查是否在舰船上
                ship = self.get_clone_ship(player, clone)
                if not ship:
                    skipped_clones.append(f"{clone['name']}（未驾驶舰船）")
                    continue
                
                target_clones.append((clone, ship))
        else:
            # 未指定克隆体：所有待机且有舰船的克隆体
            for clone in player['clones']:
                if clone['status'] == '待机':
                    ship = self.get_clone_ship(player, clone)
                    if ship:
                        target_clones.append((clone, ship))
                    else:
                        skipped_clones.append(f"{clone['name']}（未驾驶舰船）")
        
        if not target_clones:
            skip_info = "\n跳过：" + "\n".join(skipped_clones) if skipped_clones else ""
            yield event.plain_result(f"❌ 没有符合条件的克隆体可以跃迁（需要待机状态且驾驶舰船）{skip_info}")
            return
        
        # 检查是否在同一位置
        locations = set(c['location'] for c, _ in target_clones)
        if len(locations) > 1:
            loc_str = ", ".join(locations)
            yield event.plain_result(f"❌ 指定克隆体不在同一行星（当前位置：{loc_str}）")
            return
        
        current_planet = target_clones[0][0]['location']
        if current_planet == target_planet:
            yield event.plain_result(f"❌ 已经在{target_planet}了")
            return
        
        # 计算距离
        distance = self.PLANET_DISTANCES.get((current_planet, target_planet)) or self.PLANET_DISTANCES.get((target_planet, current_planet))
        if distance is None:
            distance = 1.0
        
        # 计算每个克隆体的跃迁时间（根据各自舰船速度）
        warp_skill = player['skills'].get('跃迁引擎操控', 0)
        
        # 执行跃迁 - 为每个克隆体单独计算
        warp_clones_data = []
        for clone, ship in target_clones:
            ship_speed = self.SHIP_WARP_SPEEDS.get(ship['name'], 20)
            warp_speed = ship_speed * (1 + warp_skill * 0.1)
            warp_time = distance / warp_speed  # 分钟
            
            clone['location'] = target_planet
            clone['status'] = '跃迁中'
            
            warp_clones_data.append({
                'clone_id': clone['id'],
                'clone_name': clone['name'],
                'ship_name': ship['name'],
                'speed': warp_speed,
                'duration': warp_time * 60,  # 秒
                'start_time': time.time()
            })
        
        # 保存跃迁状态（每个克隆体独立）
        player['warping'] = {
            "target": target_planet,
            "source": current_planet,
            "distance": distance,
            "clones": warp_clones_data
        }
        self.save_players()
        
        # 显示跃迁信息
        result_text = f"🚀 开始跃迁\n📍 {current_planet} → {target_planet}\n📏 距离：{distance:.2f} AU\n\n👥 跃迁克隆体：\n"
        
        for data in warp_clones_data:
            result_text += f"  {data['clone_name']}({data['ship_name']})\n"
            result_text += f"    ⚡ {data['speed']:.1f} AU/分钟 ⏱️ {data['duration']/60:.1f}分钟\n"
        
        if skipped_clones:
            result_text += "\n⏭️ 跳过（未驾驶舰船）：\n" + "\n".join(skipped_clones)
        
        result_text += "\n\n使用 /游戏跃迁状态 查看进度"
        yield event.plain_result(result_text)
    
    @filter.command("游戏跃迁状态")
    async def check_warp(self, event: AstrMessageEvent):
        """查看跃迁状态 - 显示每个克隆体独立的跃迁进度"""
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        # 先尝试结算跃迁
        completed_clones = self.settle_warp(player)
        
        # 如果结算后没有跃迁了，返回结算结果
        if not player.get('warping'):
            self.save_players()
            if completed_clones:
                yield event.plain_result(f"✅ 跃迁完成！\n已到达：{completed_clones}")
            else:
                yield event.plain_result("❌ 当前没有进行跃迁")
            return
        
        # 显示跃迁状态（每个克隆体独立显示）
        warping = player['warping']
        status_text = f"🚀 跃迁进行中\n📍 {warping['source']} → {warping['target']}\n📏 距离：{warping['distance']:.2f} AU\n\n"
        
        for clone_data in warping['clones']:
            clone_id = clone_data['clone_id']
            clone = next((c for c in player['clones'] if c['id'] == clone_id), None)
            if not clone:
                continue
            
            # 计算该克隆体的进度
            elapsed = time.time() - clone_data['start_time']
            duration = clone_data['duration']
            remaining = max(0, duration - elapsed)
            progress = min(100, (elapsed / duration) * 100)
            
            status_text += f"👤 {clone_data['clone_name']} ({clone_data['ship_name']})\n"
            status_text += f"   ⚡ {clone_data['speed']:.1f} AU/分钟\n"
            status_text += f"   ⏱️ 剩余：{remaining/60:.1f}分钟  📊 {progress:.1f}%\n\n"
        
        self.save_players()
        yield event.plain_result(status_text)
    
    def settle_warp(self, player: Dict) -> str:
        """结算跃迁 - 分别检查每个克隆体是否到达"""
        if not player.get('warping'):
            return ""
        
        warping = player['warping']
        target = warping['target']
        source = warping['source']
        completed_clones = []
        still_warping = []
        
        for clone_data in warping['clones']:
            clone_id = clone_data['clone_id']
            elapsed = time.time() - clone_data['start_time']
            
            if elapsed >= clone_data['duration']:
                # 该克隆体跃迁完成
                clone = next((c for c in player['clones'] if c['id'] == clone_id), None)
                if clone:
                    clone['status'] = '待机'
                    clone['location'] = target
                    completed_clones.append(clone_data['clone_name'])
                    
                    # 移动舰船到目标行星
                    if source in player['assets']:
                        if target not in player['assets']:
                            player['assets'][target] = {"minerals": {}, "ships": []}
                        
                        ship_id = clone.get('ship_id')
                        if ship_id:
                            for i, ship in enumerate(player['assets'][source]['ships']):
                                if ship['id'] == ship_id:
                                    ship_to_move = player['assets'][source]['ships'].pop(i)
                                    player['assets'][target]['ships'].append(ship_to_move)
                                    break
            else:
                # 仍在跃迁中
                still_warping.append(clone_data)
        
        # 更新跃迁状态
        if still_warping:
            warping['clones'] = still_warping
        else:
            # 所有克隆体都完成了
            player['warping'] = None
        
        return ", ".join(completed_clones) if completed_clones else ""

    def settle_combat(self, player: Dict) -> str:
        """结算战斗 - 占位符，待实现"""
        if not player.get('combat'):
            return ""
        # TODO: 实现战斗结算逻辑
        return ""

    def settle_manufacturing(self, player: Dict) -> str:
        """结算制造 - 占位符，待实现"""
        if not player.get('manufacturing'):
            return ""
        # TODO: 实现制造结算逻辑
        return ""

    # ========== 资产系统 ==========
    
    def format_planet_assets(self, player: Dict, planet: str) -> str:
        """格式化单个行星的资产信息"""
        text = f"{'='*30}\n"
        text += f"📍 {planet}\n"
        text += f"{'='*30}\n"
        
        # 1. 显示在该行星的克隆体
        clones_here = [c for c in player['clones'] if c['location'] == planet]
        if clones_here:
            text += "👥 克隆体：\n"
            for clone in clones_here:
                ship = self.get_clone_ship(player, clone)
                ship_info = f"驾驶 {ship['name']}" if ship else "未驾驶舰船"
                status_icon = "🟢" if clone['status'] == '待机' else "🔴"
                text += f"  {status_icon} {clone['name']} - {ship_info} ({clone['status']})\n"
        else:
            text += "👥 克隆体：无\n"
        
        # 2. 显示机库中的舰船
        ships = player['assets'].get(planet, {}).get('ships', [])
        idle_ships = [s for s in ships if not any(c.get('ship_id') == s['id'] for c in player['clones'])]
        
        if idle_ships:
            text += "🚀 机库空闲舰船：\n"
            for ship in idle_ships:
                cargo_info = self.get_ship_cargo_info(ship['name'])
                text += f"  ID:{ship['id']} {ship['name']} (血量:{ship.get('hp_percent', 100)}%){cargo_info}\n"
        else:
            text += "🚀 机库空闲舰船：无\n"
        
        # 3. 显示矿物详情（每种矿物分别显示）
        minerals = player['assets'].get(planet, {}).get('minerals', {})
        if minerals:
            text += "⛏️ 矿物库存：\n"
            for mineral_name in sorted(minerals.keys()):
                tons = minerals[mineral_name]
                text += f"  {mineral_name}：{tons:.2f}吨\n"
        else:
            text += "⛏️ 矿物库存：无\n"
        
        return text
    
    @filter.command("游戏资产")
    async def check_assets(self, event: AstrMessageEvent):
        """查看资产 - 支持指定行星或显示所有行星（假装实时刷新挖矿进度）"""
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        args = event.message_str.split()[1:]
        
        # 假装实时刷新：保存挖矿进度到仓库（不停止挖矿）
        if player['mining']:
            self.save_mining_progress(player)
        
        if len(args) >= 1:
            # 指定了行星
            planet = args[0]
            if planet not in self.VALID_PLANETS:
                yield event.plain_result(f"❌ 无效行星。可选：{', '.join(self.VALID_PLANETS)}")
                return
            
            # 显示指定行星的资产
            assets_text = f"📦 {planet}资产\n\n💰 钱包：¥{player['wallet']:,}\n\n"
            assets_text += self.format_planet_assets(player, planet)
        else:
            # 显示所有行星的资产
            assets_text = f"📦 资产总览\n\n💰 钱包：¥{player['wallet']:,}\n"
            
            # 获取所有行星列表（包括有资产的和克隆体所在的）
            all_planets = set(player['assets'].keys())
            for clone in player['clones']:
                all_planets.add(clone['location'])
            
            for planet in sorted(all_planets):
                assets_text += "\n" + self.format_planet_assets(player, planet)
        
        yield event.plain_result(assets_text)

    # ========== 辅助方法 ==========
    
    def get_clone_ship(self, player: Dict, clone: Dict):
        """获取克隆体当前驾驶的舰船信息"""
        if clone.get('ship_id') is None:
            return None
        
        # 获取实际所在行星（处理小行星带的情况）
        location = clone['location']
        if '小行星带' in location:
            location = location.replace('小行星带', '')
        
        for ship in player['assets'].get(location, {}).get('ships', []):
            if ship['id'] == clone['ship_id']:
                return ship
        return None
    
    def get_ship_cargo_info(self, ship_name: str, current_cargo: int = 0) -> str:
        """获取舰船货仓信息（仅运输船）"""
        # 只显示运输船的货仓，采矿船自动卸载不需要显示
        cargo_capacities = {
            "崆峒级运输舰": 60000,
            "泰山级货舰": 2000000
        }
        capacity = cargo_capacities.get(ship_name, 0)
        if capacity > 0:
            return f" 货仓{current_cargo}/{capacity}m³"
        return ""
    
    def get_ship_cargo_capacity(self, ship_name: str, player: Dict = None) -> int:
        """获取舰船货仓容量（受货运管理技能影响）"""
        base_capacities = {
            "蜜蜂级采矿护卫舰": 500,
            "蝗虫级采矿驳船": 3000,
            "崆峒级运输舰": 60000,
            "泰山级货舰": 2000000
        }
        base_capacity = base_capacities.get(ship_name, 0)
        
        if player and base_capacity > 0 and ship_name in ["崆峒级运输舰", "泰山级货舰"]:
            # 货运管理技能加成：每级+10%容量（仅运输船）
            cargo_skill = player['skills'].get('货运管理', 0)
            bonus = 1 + cargo_skill * 0.1
            return int(base_capacity * bonus)
        
        return base_capacity
    
    def is_transport_ship(self, ship_name: str) -> bool:
        """检查是否为运输船"""
        return ship_name in ["崆峒级运输舰", "泰山级货舰"]
    
    def get_ship_total_cargo_volume(self, ship: Dict) -> float:
        """计算舰船货仓中货物的总体积(m³)"""
        cargo = ship.get('cargo', {})
        total_volume = 0
        # 矿物体积表(m³/吨)
        mineral_volumes = {
            "硫": 0.483, "铁": 0.127, "镁": 0.575, "硅": 0.429,
            "铝": 0.370, "锰": 0.137, "锌": 0.140,
            "铅": 0.088, "钛": 0.222, "铬": 0.139, "锑": 0.150,
            "锂": 1.887, "铜": 0.112, "镍": 0.112, "锡": 0.137,
            "钴": 0.112, "钼": 0.097, "铌": 0.117, "钨": 0.052, "钒": 0.164
        }
        for mineral, tons in cargo.items():
            volume_per_ton = mineral_volumes.get(mineral, 0.5)
            total_volume += tons * volume_per_ton
        return total_volume

    def parse_cargo_list(self, cargo_str: str, planet_minerals: Dict = None, ship_cargo: Dict = None, is_load: bool = True) -> Dict[str, float]:
        """解析货物列表字符串
        支持格式：
        - '硫:100,铁:50' -> 指定数量
        - '硫,铁' -> 不指定数量，全部装载/卸载
        """
        cargo = {}
        items = cargo_str.split(',')
        for item in items:
            item = item.strip()
            if not item:
                continue
            
            if ':' in item:
                # 指定数量
                parts = item.split(':')
                mineral = parts[0].strip()
                try:
                    tons = float(parts[1].strip())
                    if tons > 0:
                        cargo[mineral] = tons
                except ValueError:
                    continue
            else:
                # 不指定数量，全部装载/卸载
                mineral = item
                if is_load and planet_minerals:
                    # 装载：全部行星上的该矿物
                    tons = planet_minerals.get(mineral, 0)
                    if tons > 0:
                        cargo[mineral] = tons
                elif not is_load and ship_cargo:
                    # 卸载：全部船上的该矿物
                    tons = ship_cargo.get(mineral, 0)
                    if tons > 0:
                        cargo[mineral] = tons
        return cargo

    @filter.command("游戏装载")
    async def load_cargo(self, event: AstrMessageEvent):
        """批量装载货物到运输船 - 支持自动处理超载（假装实时刷新挖矿进度）"""
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        # 假装实时刷新：保存挖矿进度到仓库（不停止挖矿）
        if player['mining']:
            self.save_mining_progress(player)
        
        args = event.message_str.split()[1:]
        if len(args) < 2:
            yield event.plain_result("❌ 用法：/游戏装载 <舰船ID> <矿物名:吨数,矿物名:吨数...>\n例如：/游戏装载 5 硫:100,铁:50\n或：/游戏装载 5 硫,铁（装载全部）")
            return
        
        try:
            ship_id = int(args[0])
        except ValueError:
            yield event.plain_result("❌ 舰船ID必须是数字")
            return
        
        # 找到舰船
        location = player['clones'][0]['location'] if player['clones'] else "地球"
        target_ship = None
        ship_location = None
        
        for planet in player['assets']:
            for ship in player['assets'][planet].get('ships', []):
                if ship['id'] == ship_id:
                    target_ship = ship
                    ship_location = planet
                    break
            if target_ship:
                break
        
        if not target_ship:
            yield event.plain_result(f"❌ 找不到ID为{ship_id}的舰船")
            return
        
        if not self.is_transport_ship(target_ship['name']):
            yield event.plain_result(f"❌ {target_ship['name']} 不是运输船")
            return
        
        if ship_location != location:
            yield event.plain_result(f"❌ 该舰船在{ship_location}，不在当前位置{location}")
            return
        
        # 矿物体积表
        mineral_volumes = {
            "硫": 0.483, "铁": 0.127, "镁": 0.575, "硅": 0.429,
            "铝": 0.370, "锰": 0.137, "锌": 0.140,
            "铅": 0.088, "钛": 0.222, "铬": 0.139, "锑": 0.150,
            "锂": 1.887, "铜": 0.112, "镍": 0.112, "锡": 0.137,
            "钴": 0.112, "钼": 0.097, "铌": 0.117, "钨": 0.052, "钒": 0.164
        }
        
        # 解析货物列表（支持不指定数量）
        planet_minerals = player['assets'].get(location, {}).get('minerals', {})
        cargo_str = ' '.join(args[1:])
        cargo_list = self.parse_cargo_list(cargo_str, planet_minerals=planet_minerals, is_load=True)
        
        if not cargo_list:
            yield event.plain_result("❌ 货物格式错误或没有可装载的货物\n格式：矿物名:吨数,矿物名:吨数... 或 矿物名,矿物名...")
            return
        
        # 检查货物是否足够
        errors = []
        for mineral, tons in list(cargo_list.items()):
            available = planet_minerals.get(mineral, 0)
            if available <= 0:
                errors.append(f"{mineral}在{location}没有库存")
                del cargo_list[mineral]
            elif available < tons:
                # 库存不足，调整为全部库存
                cargo_list[mineral] = available
        
        if not cargo_list:
            yield event.plain_result("❌ 没有可装载的货物：\n" + "\n".join(errors))
            return
        
        # 检查货仓容量，自动处理超载
        capacity = self.get_ship_cargo_capacity(target_ship['name'], player)
        current_volume = self.get_ship_total_cargo_volume(target_ship)
        remaining_volume = capacity - current_volume
        
        # 计算需要的总体积
        total_volume = 0
        for mineral, tons in cargo_list.items():
            volume = tons * mineral_volumes.get(mineral, 0.5)
            total_volume += volume
        
        # 如果超载，按比例减少装载量
        skipped_minerals = []
        if total_volume > remaining_volume:
            # 按体积从小到大排序，优先装载体积小的矿物
            sorted_cargo = sorted(cargo_list.items(), key=lambda x: mineral_volumes.get(x[0], 0.5))
            
            new_cargo_list = {}
            for mineral, tons in sorted_cargo:
                volume_per_ton = mineral_volumes.get(mineral, 0.5)
                max_tons = remaining_volume / volume_per_ton
                
                if max_tons <= 0:
                    # 空间已满，这个矿物无法装载
                    skipped_minerals.append(f"{mineral}（空间不足）")
                    continue
                
                actual_tons = min(tons, max_tons)
                new_cargo_list[mineral] = actual_tons
                remaining_volume -= actual_tons * volume_per_ton
            
            cargo_list = new_cargo_list
        
        if not cargo_list:
            yield event.plain_result(f"❌ 货仓空间不足（剩余{capacity - current_volume:.1f}m³），无法装载任何货物")
            return
        
        # 执行批量装载
        if 'cargo' not in target_ship:
            target_ship['cargo'] = {}
        
        loaded_summary = []
        for mineral, tons in cargo_list.items():
            if mineral not in target_ship['cargo']:
                target_ship['cargo'][mineral] = 0
            target_ship['cargo'][mineral] += tons
            planet_minerals[mineral] -= tons
            if planet_minerals[mineral] <= 0:
                del planet_minerals[mineral]
            loaded_summary.append(f"  {mineral}：{tons:.2f}吨")
        
        self.save_players()
        
        new_volume = self.get_ship_total_cargo_volume(target_ship)
        result_text = f"✅ 装载完成\n舰船：{target_ship['name']} (ID:{ship_id})\n\n装载货物：\n" + "\n".join(loaded_summary)
        
        if skipped_minerals:
            result_text += "\n\n⏭️ 未装载（空间不足）：\n" + "\n".join([f"  {s}" for s in skipped_minerals])
        
        result_text += f"\n\n货仓：{new_volume:.1f}/{capacity}m³"
        yield event.plain_result(result_text)

    @filter.command("游戏卸载")
    async def unload_cargo(self, event: AstrMessageEvent):
        """批量从运输船卸载货物 - 支持不指定数量（全部卸载）"""
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        args = event.message_str.split()[1:]
        if len(args) < 2:
            yield event.plain_result("❌ 用法：/游戏卸载 <舰船ID> <矿物名:吨数,矿物名:吨数...>\n例如：/游戏卸载 5 硫:100,铁:50\n或：/游戏卸载 5 硫,铁（卸载全部）")
            return
        
        try:
            ship_id = int(args[0])
        except ValueError:
            yield event.plain_result("❌ 舰船ID必须是数字")
            return
        
        # 找到舰船
        location = player['clones'][0]['location'] if player['clones'] else "地球"
        target_ship = None
        ship_location = None
        
        for planet in player['assets']:
            for ship in player['assets'][planet].get('ships', []):
                if ship['id'] == ship_id:
                    target_ship = ship
                    ship_location = planet
                    break
            if target_ship:
                break
        
        if not target_ship:
            yield event.plain_result(f"❌ 找不到ID为{ship_id}的舰船")
            return
        
        if not self.is_transport_ship(target_ship['name']):
            yield event.plain_result(f"❌ {target_ship['name']} 不是运输船")
            return
        
        if ship_location != location:
            yield event.plain_result(f"❌ 该舰船在{ship_location}，不在当前位置{location}")
            return
        
        # 解析货物列表（支持不指定数量）
        ship_cargo = target_ship.get('cargo', {})
        cargo_str = ' '.join(args[1:])
        cargo_list = self.parse_cargo_list(cargo_str, ship_cargo=ship_cargo, is_load=False)
        
        if not cargo_list:
            yield event.plain_result("❌ 货物格式错误或货仓中没有这些矿物\n格式：矿物名:吨数,矿物名:吨数... 或 矿物名,矿物名...")
            return
        
        # 检查货仓中是否有足够的货物
        errors = []
        for mineral, tons in list(cargo_list.items()):
            available = ship_cargo.get(mineral, 0)
            if available <= 0:
                errors.append(f"{mineral}在货仓中没有库存")
                del cargo_list[mineral]
            elif available < tons:
                # 库存不足，调整为全部库存
                cargo_list[mineral] = available
        
        if not cargo_list:
            yield event.plain_result("❌ 没有可卸载的货物：\n" + "\n".join(errors))
            return
        
        # 执行批量卸载
        if location not in player['assets']:
            player['assets'][location] = {"minerals": {}, "ships": []}
        if 'minerals' not in player['assets'][location]:
            player['assets'][location]['minerals'] = {}
        
        unloaded_summary = []
        for mineral, tons in cargo_list.items():
            ship_cargo[mineral] -= tons
            if ship_cargo[mineral] <= 0:
                del ship_cargo[mineral]
            
            if mineral not in player['assets'][location]['minerals']:
                player['assets'][location]['minerals'][mineral] = 0
            player['assets'][location]['minerals'][mineral] += tons
            unloaded_summary.append(f"  {mineral}：{tons:.2f}吨")
        
        self.save_players()
        
        capacity = self.get_ship_cargo_capacity(target_ship['name'], player)
        new_volume = self.get_ship_total_cargo_volume(target_ship)
        result_text = f"✅ 卸载完成\n舰船：{target_ship['name']} (ID:{ship_id})\n\n卸载货物：\n" + "\n".join(unloaded_summary)
        result_text += f"\n\n货仓：{new_volume:.1f}/{capacity}m³"
        yield event.plain_result(result_text)

    @filter.command("游戏机库")
    async def list_hangar(self, event: AstrMessageEvent):
        """查看机库中的舰船 - 支持指定行星，显示运输船货仓（假装实时刷新挖矿进度）"""
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        # 假装实时刷新：保存挖矿进度到仓库（不停止挖矿）
        if player['mining']:
            self.save_mining_progress(player)
        
        args = event.message_str.split()[1:]
        
        if len(args) >= 1:
            # 指定了行星
            location = args[0]
            if location not in self.VALID_PLANETS:
                yield event.plain_result(f"❌ 无效行星。可选：{', '.join(self.VALID_PLANETS)}")
                return
        else:
            # 默认当前所在行星
            location = player['clones'][0]['location'] if player['clones'] else "地球"
        
        ships = player['assets'].get(location, {}).get('ships', [])
        
        if not ships:
            yield event.plain_result(f"📦 {location}机库\n\n暂无舰船")
            return
        
        hangar_text = f"📦 {location}机库\n\n"
        
        # 分类显示：作战船、采矿船、运输船
        combat_ships = []
        mining_ships = []
        transport_ships = []
        
        for ship in ships:
            status = "🚀 已装备" if any(c.get('ship_id') == ship['id'] for c in player['clones']) else "⚓ 待命"
            ship_info = (ship, status)
            
            if ship['name'] in ["狂风级护卫舰", "骤雨级驱逐舰", "烈火级巡洋舰", "怒雷级战列舰"]:
                combat_ships.append(ship_info)
            elif ship['name'] in ["蜜蜂级采矿护卫舰", "蝗虫级采矿驳船"]:
                mining_ships.append(ship_info)
            elif ship['name'] in ["崆峒级运输舰", "泰山级货舰"]:
                transport_ships.append(ship_info)
        
        # 显示作战船
        if combat_ships:
            hangar_text += "⚔️ 作战舰船：\n"
            for ship, status in combat_ships:
                hangar_text += f"  ID:{ship['id']} {ship['name']} (血量:{ship.get('hp_percent', 100)}%) {status}\n"
            hangar_text += "\n"
        
        # 显示采矿船
        if mining_ships:
            hangar_text += "⛏️ 采矿舰船：\n"
            for ship, status in mining_ships:
                hangar_text += f"  ID:{ship['id']} {ship['name']} (血量:{ship.get('hp_percent', 100)}%) {status}\n"
            hangar_text += "\n"
        
        # 显示运输船（包含货仓信息）
        if transport_ships:
            hangar_text += "🚛 运输舰船：\n"
            for ship, status in transport_ships:
                capacity = self.get_ship_cargo_capacity(ship['name'], player)
                cargo = ship.get('cargo', {})
                used_volume = self.get_ship_total_cargo_volume(ship)
                hangar_text += f"  ID:{ship['id']} {ship['name']} (血量:{ship.get('hp_percent', 100)}%) {status}\n"
                hangar_text += f"    货仓：{used_volume:.1f}/{capacity}m³ ({len(cargo)}种货物)\n"
                if cargo:
                    for mineral, tons in sorted(cargo.items()):
                        hangar_text += f"      - {mineral}：{tons:.2f}吨\n"
            hangar_text += "\n"
        
        hangar_text += "使用 /游戏换船 <克隆体编号> <舰船ID> 更换舰船\n"
        hangar_text += "使用 /游戏离舰 <克隆体编号> 让克隆体离舰\n"
        if transport_ships:
            hangar_text += "使用 /游戏装载 <舰船ID> <矿物名:吨数,矿物名:吨数...> 批量装载\n"
            hangar_text += "使用 /游戏卸载 <舰船ID> <矿物名:吨数,矿物名:吨数...> 批量卸载"
        
        yield event.plain_result(hangar_text)
