from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import json
import os
import time
import random
import asyncio
from typing import Dict, List, Optional, Tuple
from collections import deque

# 插件版本号
PLUGIN_VERSION = "3.0.1"

@register("astrbot_plugin_SGDGame", "LZQ123PKQ", "星际黎明 - 太空挂机游戏插件", PLUGIN_VERSION, "https://github.com/LZQ123PKQ/astrbot_plugin_SGDgame")
class SGDGamePlugin(Star):
    # 数据版本号，与插件版本保持一致，每次数据结构变更时更新 PLUGIN_VERSION
    DATA_VERSION = PLUGIN_VERSION
    MARKET_DATA_VERSION = PLUGIN_VERSION
    ESCROW_DATA_VERSION = PLUGIN_VERSION

    def __init__(self, context: Context):
        super().__init__(context)
        # 硬编码数据目录路径
        self.data_dir = "/root/AstrBot/data/plugin_data/astrbot_plugin_SGDgame"
        os.makedirs(self.data_dir, exist_ok=True)
        self.players_file = os.path.join(self.data_dir, "players.json")
        self.players = self.load_players()
        # 市场系统数据文件
        self.market_file = os.path.join(self.data_dir, "market.json")
        self.escrow_file = os.path.join(self.data_dir, "escrow.json")
        self.market_data = self.load_market()
        self.escrow_data = self.load_escrow()
        # ID生成计数器，避免时间戳冲突
        self._order_id_counter = 0
        self._escrow_id_counter = 0
        # 启动自动结算任务
        self.ratting_settle_task = asyncio.create_task(self._ratting_auto_settle_loop())
        logger.info(f"星际黎明插件已加载 (版本: {PLUGIN_VERSION})")

    def _generate_order_id(self) -> str:
        """生成唯一的订单ID"""
        self._order_id_counter += 1
        return f"ORD{int(time.time() * 1000)}-{self._order_id_counter}"

    def _generate_escrow_id(self) -> str:
        """生成唯一的中介ID"""
        self._escrow_id_counter += 1
        return f"ESC{int(time.time() * 1000)}-{self._escrow_id_counter}"

    async def terminate(self):
        """插件被卸载/停用时会调用"""
        logger.info("星际黎明插件正在卸载...")
        # 取消自动结算任务
        if self.ratting_settle_task:
            self.ratting_settle_task.cancel()
            try:
                await self.ratting_settle_task
            except asyncio.CancelledError:
                pass
        logger.info("星际黎明插件已卸载")

    def load_players(self) -> Dict:
        """加载玩家数据，自动迁移旧版本数据"""
        if os.path.exists(self.players_file):
            with open(self.players_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 数据迁移
                return self._migrate_players_data(data)
        return {}

    def _migrate_players_data(self, data: Dict) -> Dict:
        """迁移玩家数据到最新版本"""
        for user_id, player in data.items():
            # 确保版本号字段存在（旧版本可能是整数或不存在）
            if 'data_version' not in player:
                player['data_version'] = "0.0.0"
            elif isinstance(player['data_version'], int):
                # 兼容旧版本的整数版本号
                player['data_version'] = f"1.{player['data_version']}.0"
            
            # 确保所有必需字段存在
            if 'wallet' not in player:
                player['wallet'] = 0
            if 'name' not in player:
                player['name'] = '飞行员'
            if 'status' not in player:
                player['status'] = '待机'
            if 'ship_id' not in player:
                player['ship_id'] = 1
            if 'location' not in player:
                player['location'] = '吉他'
            if 'assets' not in player:
                player['assets'] = {}
            if 'next_ship_id' not in player:
                player['next_ship_id'] = 2
            
            # 确保活动状态字段存在
            if 'mining' not in player:
                player['mining'] = None
            if 'manufacturing' not in player:
                player['manufacturing'] = None
            if 'navigating' not in player:
                player['navigating'] = None
            if 'ratting' not in player:
                player['ratting'] = None
            if 'transporting' not in player:
                player['transporting'] = None
            
            # 确保每个星系的资产结构完整
            for system, assets in player['assets'].items():
                if 'minerals' not in assets:
                    assets['minerals'] = {}
                if 'ores' not in assets:
                    assets['ores'] = {}
                if 'ships' not in assets:
                    assets['ships'] = []
                
                # 确保舰船数据结构完整
                for ship in assets.get('ships', []):
                    if 'cargo' not in ship:
                        ship['cargo'] = {}
                    if 'ore_hold' not in ship:
                        ship['ore_hold'] = {}
            
            # 更新版本号
            player['data_version'] = self.DATA_VERSION
        
        return data

    def save_players(self):
        """保存玩家数据"""
        # 确保所有玩家数据都有版本号
        for user_id, player in self.players.items():
            if 'data_version' not in player:
                player['data_version'] = self.DATA_VERSION
        with open(self.players_file, 'w', encoding='utf-8') as f:
            json.dump(self.players, f, ensure_ascii=False, indent=2)

    def load_market(self) -> Dict:
        """加载市场数据，自动迁移旧版本数据"""
        if os.path.exists(self.market_file):
            with open(self.market_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return self._migrate_market_data(data)
        # 默认初始化吉他市场
        return {"吉他": [], "data_version": self.MARKET_DATA_VERSION}

    def _migrate_market_data(self, data: Dict) -> Dict:
        """迁移市场数据到最新版本"""
        # 确保版本号字段存在（旧版本可能是整数或不存在）
        if 'data_version' not in data:
            data['data_version'] = "0.0.0"
        elif isinstance(data['data_version'], int):
            # 兼容旧版本的整数版本号
            data['data_version'] = f"1.{data['data_version']}.0"
        
        # 确保吉他市场存在
        if '吉他' not in data:
            data['吉他'] = []
        
        # 验证每个订单的结构完整性
        for order in data.get('吉他', []):
            if 'order_id' not in order:
                order['order_id'] = self._generate_order_id()
            if 'type' not in order:
                order['type'] = 'sell'
            if 'item_name' not in order:
                order['item_name'] = '未知物品'
            if 'quantity' not in order:
                order['quantity'] = 0
            if 'price' not in order:
                order['price'] = 0
            if 'escrow_id' not in order:
                order['escrow_id'] = ''
            if 'created_at' not in order:
                order['created_at'] = time.time()
        
        # 更新版本号
        data['data_version'] = self.MARKET_DATA_VERSION
        return data

    def save_market(self):
        """保存市场数据"""
        # 确保版本号存在
        if 'data_version' not in self.market_data:
            self.market_data['data_version'] = self.MARKET_DATA_VERSION
        with open(self.market_file, 'w', encoding='utf-8') as f:
            json.dump(self.market_data, f, ensure_ascii=False, indent=2)

    def load_escrow(self) -> Dict:
        """加载中介冻结数据，自动迁移旧版本数据"""
        if os.path.exists(self.escrow_file):
            with open(self.escrow_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return self._migrate_escrow_data(data)
        return {"data_version": self.ESCROW_DATA_VERSION}

    def _migrate_escrow_data(self, data: Dict) -> Dict:
        """迁移中介数据到最新版本"""
        # 确保版本号字段存在（旧版本可能是整数或不存在）
        if 'data_version' not in data:
            data['data_version'] = "0.0.0"
        elif isinstance(data['data_version'], int):
            # 兼容旧版本的整数版本号
            data['data_version'] = f"1.{data['data_version']}.0"
        
        # 验证每个中介记录的结构完整性
        for escrow_id, escrow in list(data.items()):
            if escrow_id == 'data_version':
                continue
            
            if not isinstance(escrow, dict):
                continue
            
            if 'escrow_id' not in escrow:
                escrow['escrow_id'] = escrow_id
            if 'type' not in escrow:
                escrow['type'] = 'item'
            if 'item_name' not in escrow:
                escrow['item_name'] = '未知物品'
            if 'quantity' not in escrow:
                escrow['quantity'] = 0
            if 'owner_id' not in escrow:
                escrow['owner_id'] = ''
            if 'status' not in escrow:
                escrow['status'] = 'frozen'
            if 'created_at' not in escrow:
                escrow['created_at'] = time.time()
        
        # 更新版本号
        data['data_version'] = self.ESCROW_DATA_VERSION
        return data

    def save_escrow(self):
        """保存中介冻结数据"""
        # 确保版本号存在
        if 'data_version' not in self.escrow_data:
            self.escrow_data['data_version'] = self.ESCROW_DATA_VERSION
        with open(self.escrow_file, 'w', encoding='utf-8') as f:
            json.dump(self.escrow_data, f, ensure_ascii=False, indent=2)

    def get_player(self, user_id: str) -> Dict:
        """获取玩家数据，单角色模式，自动初始化新玩家"""
        self.players = self.load_players()
        if user_id not in self.players:
            self.players[user_id] = self._create_default_player()
            self.save_players()
            logger.info(f"新玩家 {user_id} 已创建")
        return self.players[user_id]

    def _create_default_player(self) -> Dict:
        """创建默认玩家数据结构"""
        return {
            "wallet": 0,
            "name": "飞行员",
            "status": "待机",
            "ship_id": 1,
            "location": "吉他",
            "assets": {
                "吉他": {
                    "minerals": {},
                    "ores": {},
                    "ships": [
                        {
                            "id": 1,
                            "name": "冲锋者级",
                            "hp_percent": 100,
                            "cargo": {},
                            "ore_hold": {}
                        }
                    ]
                }
            },
            "next_ship_id": 2,
            "mining": None,
            "manufacturing": None,
            "navigating": None,
            "ratting": None,
            "transporting": None,
            "data_version": self.DATA_VERSION  # 记录数据版本
        }

    # ========== 舰船数据 ==========
    # volume: 舰船体积(m³)，用于货柜装载计算（简化值）
    SHIPS_DATA = {
        "小鹰级": {"type": "作战", "dps": 305.4, "hp": 7816, "cargo": 150.0, "volume": 2500, "warp": 5.0, "align": 3},
        "海燕级": {"type": "作战", "dps": 507, "hp": 10618, "cargo": 425, "volume": 5000, "warp": 4.5, "align": 4},
        "巨鸟级": {"type": "作战", "dps": 774.5, "hp": 49652, "cargo": 450, "volume": 10000, "warp": 4.0, "align": 5},
        "娜迦级": {"type": "作战", "dps": 1439.4, "hp": 53984, "cargo": 575, "volume": 15000, "warp": 3.5, "align": 7},
        "鹏鲲级": {"type": "作战", "dps": 1405.7, "hp": 142671, "cargo": 820, "volume": 50000, "warp": 3.0, "align": 13},
        "冲锋者级": {"type": "采矿", "dps": 39.6, "hp": 5378, "cargo": 50.0, "volume": 2500, "ore_hold": 5000, "mining": 8.51, "warp": 5.0, "align": 4},
        "回旋者级": {"type": "采矿", "dps": 99.0, "hp": 14091, "cargo": 450.0, "volume": 3750, "ore_hold": 27500, "mining": 20.96, "warp": 3.0, "align": 12},
        "狐鼬级": {"type": "运输", "dps": 49.3, "hp": 14364, "cargo": 24114.2, "volume": 20000, "warp": 4.7, "align": 11},
        "渡神级": {"type": "运输", "dps": 0, "hp": 215993, "cargo": 1204740.5, "volume": 1300000, "warp": 1.4, "align": 42},
    }
    
    # ========== 星系数据 ==========
    
    def get_npc_station_systems(self) -> List[str]:
        """获取所有有NPC空间站的星系（高安和低安，安等 >= 0.0）"""
        return [system for system, security in self.SYSTEM_SECURITY.items() if security >= 0.0]
    
    def find_nearest_npc_station(self, start_system: str) -> Optional[str]:
        """使用BFS查找最近的NPC空间站星系
        
        Args:
            start_system: 起始星系
            
        Returns:
            最近的NPC空间站星系名称，如果没有找到则返回None
        """
        if start_system not in self.GATE_CONNECTIONS:
            return None
        
        # 如果当前星系就是NPC空间站，直接返回
        if self.SYSTEM_SECURITY.get(start_system, -1) >= 0.0:
            return start_system
        
        # BFS查找
        npc_systems = set(self.get_npc_station_systems())
        visited = {start_system}
        queue = deque([(start_system, 0)])  # (星系, 距离)
        
        while queue:
            current, distance = queue.popleft()
            
            # 检查当前星系是否是NPC空间站
            if current in npc_systems:
                return current
            
            # 遍历相邻星系
            for neighbor in self.GATE_CONNECTIONS.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, distance + 1))
        
        return None  # 没有找到NPC空间站
    
    SYSTEM_SECURITY = {
        # 伏尔戈星域 - 木本呂星座
        "新加达里": 1.000, "皮尔米特": 0.953, "尼亚拜伦": 0.964, "吉他": 0.946,
        "基索加": 1.000, "玛乌纳斯": 0.913, "乌尔仑": 0.960,
        # 伏尔戈星域 - 伊西拉肯星座
        "安斯拉": 0.912, "希尔塔蒙": 0.975, "西卡塔": 0.824, "欧图尼": 0.734,
        "奥马海仑": 0.664, "尤斯库仑": 0.625, "伊库奇": 0.987, "奥坎尼托": 0.971,
        # 伏尔戈星域 - 奥尼尔瓦纳星座
        "欧罗": 0.676, "乔萨密陀": 0.578, "奥班伦": 0.562, "列库里": 0.601, "波耶伦": 0.558,
        # 伏尔戈星域 - 诺莫星座
        "阿图莱玛": 0.613, "基尔玛贝": 0.732, "瓦安卡伦": 0.647, "玛提斯塔": 0.658,
        "贾塔特": 0.637, "密茨伦": 0.634, "伊塔莫": 0.672,
        # 伏尔戈星域 - 安塔勒恩星座
        "乌伊特里拉": 0.924, "诺玛尔": 0.607, "什胡肯": 0.875, "乌恩帕斯": 0.946,
        "图乌瑞纳": 0.611, "希尔瑟讷": 0.748, "基尔拉斯": 0.650,
        # 伏尔戈星域 - 欧柯蒙星座
        "哈比伦": 0.541, "欧约伦": 0.699, "胡尔托肯": 0.586, "格昆塔米": 0.699,
        "贾卡纳尔维": 0.743, "埃巴加瓦": 0.625, "赛西奥": 0.652,
        # 伏尔戈星域 - 以哈塔罗星座
        "马伊拉": 0.441, "米瑟约亚": 0.315, "爱科拉": 0.325, "普尔乔拉": 0.521,
        "莱伊森": 0.519, "伊卡密": 0.532,
        # 伏尔戈星域 - 欧特萨贝拉星座
        "斯勒恩": 0.522, "埃吉伦": 0.689, "乌卡伦": 0.645, "科伊卡肯": 0.721,
        "索什恩": 0.634, "温努斯": 0.740, "瓦托伦": 0.708,
        # 伏尔戈星域 - 欧克勒恩星座
        "伊什索蒙": 0.651, "艾尔米亚": 0.623, "萨基凯伦": 0.595, "弗瑞吉": 0.509,
        "以哈坎拿": 0.381, "瓦胡诺米": 0.532, "欧提托": 0.482, "欧塔迈伦": 0.479,
        # 伏尔戈星域 - 奥拉日星座
        "欧斯蒙": 0.680, "库尔斯基": 0.643, "因纳亚": 0.552, "鲁肯": 0.761,
        "乌米纳斯": 0.484, "艾拉肯": 0.504, "欧加仑": 0.352, "乌欧斯": 0.562,
        # 伏尔戈星域 - 米沃拉星座
        "埃加奥": 0.162, "夫斯库仑": 0.225, "帕拉": 0.134, "尤蒙": 0.197,
        "奥塔希拉": 0.238, "塔瑟提": 0.282,
        # 伏尔戈星域 - 厄沙拉星座
        "欧特色拉": 0.384, "沃斯基奥": 0.500, "瓦尔瓦林": 0.379, "瓦萨拉": 0.494,
        "吉安提": 0.529, "恒托加拉": 0.567,
        # 伏尔戈星域 - 厄尔帕纳星座
        "奥斯阿": 0.329, "欧贝": 0.347, "欧库仑": 0.385, "伊卢卡": 0.417,
        "马斯塔克蒙": 0.457, "乌查什": 0.474,
        # 辛迪加星域 - 盖伦特边境地区星座
        "伊恩-奥斯塔": 0.780,
        # 赛塔德洱星域
        "伊纳洛": 0.837, "姆沃莱伦": 0.708, "阿里卡拉": 0.711, "希尔帕拉": 0.883, "库索蒙莫": 0.847,
        # 吉勒西斯星域 - 纳茨迪尔星座
        "阿巴宗": 0.421,
        # 长征星域
        "吞塔拉斯": 0.885, "索巴色基": 0.841, "莫卡冷": 0.948, "哈克农": 0.296,
        # 静寂谷星域 - Z-DO53星座
        "P3EN-E": -0.275,
        # 对舞之域星域
        "EOA-ZC": -0.071, "BWF-ZZ": -0.575,
        # 美特伯里斯星域
        "托蒂弗伦": 0.116, "欧法戈": 0.292,
        # 琉蓝之穹星域 - 8AO-5V星座
        "LXQ2-T": -0.077,
    }
    
    # 星域-星座-星系层级结构
    REGIONS = {
        "伏尔戈": {
            "木本呂": ["新加达里", "皮尔米特", "尼亚拜伦", "吉他", "基索加", "玛乌纳斯", "乌尔仑"],
            "伊西拉肯": ["安斯拉", "希尔塔蒙", "西卡塔", "欧图尼", "奥马海仑", "尤斯库仑", "伊库奇", "奥坎尼托"],
            "奥尼尔瓦纳": ["欧罗", "乔萨密陀", "奥班伦", "列库里", "波耶伦"],
            "诺莫": ["阿图莱玛", "基尔玛贝", "瓦安卡伦", "玛提斯塔", "贾塔特", "密茨伦", "伊塔莫"],
            "安塔勒恩": ["乌伊特里拉", "诺玛尔", "什胡肯", "乌恩帕斯", "图乌瑞纳", "希尔瑟讷", "基尔拉斯"],
            "欧柯蒙": ["哈比伦", "欧约伦", "胡尔托肯", "格昆塔米", "贾卡纳尔维", "埃巴加瓦", "赛西奥"],
            "以哈塔罗": ["马伊拉", "米瑟约亚", "爱科拉", "普尔乔拉", "莱伊森", "伊卡密"],
            "欧特萨贝拉": ["斯勒恩", "埃吉伦", "乌卡伦", "科伊卡肯", "索什恩", "温努斯", "瓦托伦"],
            "欧克勒恩": ["伊什索蒙", "艾尔米亚", "萨基凯伦", "弗瑞吉", "以哈坎拿", "瓦胡诺米", "欧提托", "欧塔迈伦"],
            "奥拉日": ["欧斯蒙", "库尔斯基", "因纳亚", "鲁肯", "乌米纳斯", "艾拉肯", "欧加仑", "乌欧斯"],
            "米沃拉": ["埃加奥", "夫斯库仑", "帕拉", "尤蒙", "奥塔希拉", "塔瑟提"],
            "厄沙拉": ["欧特色拉", "沃斯基奥", "瓦尔瓦林", "瓦萨拉", "吉安提", "恒托加拉"],
            "厄尔帕纳": ["奥斯阿", "欧贝", "欧库仑", "伊卢卡", "马斯塔克蒙", "乌查什"],
        },
        "辛迪加": {
            "盖伦特边境": ["伊恩-奥斯塔"],
        },
        "赛塔德洱": {
            "舜": ["伊纳洛"],
            "欧塔托": ["姆沃莱伦"],
            "埃勒金": ["阿里卡拉"],
            "拜": ["希尔帕拉"],
            "达森": ["库索蒙莫"],
        },
        "吉勒西斯": {
            "纳茨迪尔": ["阿巴宗"],
        },
        "长征": {
            "欧克拉": ["吞塔拉斯"],
            "考伊奇": ["索巴色基"],
            "塞拉": ["莫卡冷"],
            "弥陀": ["哈克农"],
        },
        "静寂谷": {
            "Z-DO53": ["P3EN-E"],
        },
        "对舞之域": {
            "F-ZNNG": ["EOA-ZC"],
            "IPS-QB": ["BWF-ZZ"],
        },
        "美特伯里斯": {
            "奥铎丹": ["托蒂弗伦"],
            "因科姆": ["欧法戈"],
        },
        "琉蓝之穹": {
            "8AO-5V": ["LXQ2-T"],
        },
    }
    
    GATE_CONNECTIONS = {
        "吉他": ["伊库奇", "索巴色基", "姆沃莱伦", "皮尔米特", "新加达里", "尼亚拜伦", "玛乌纳斯"],
        "新加达里": ["希尔塔蒙", "乔萨密陀", "莫卡冷", "阿里卡拉", "尼亚拜伦", "基索加", "吉他"],
        "皮尔米特": ["吉他", "玛乌纳斯", "乌尔仑", "伊恩-奥斯塔"],
        "尼亚拜伦": ["乌尔仑", "新加达里", "吉他"],
        "基索加": ["新加达里"],
        "玛乌纳斯": ["伊塔莫", "姆沃莱伦", "吉他", "皮尔米特"],
        "乌尔仑": ["乌恩帕斯", "希尔帕拉", "库索蒙莫", "尼亚拜伦", "皮尔米特"],
        "伊库奇": ["安斯拉", "希尔塔蒙", "吉他", "吞塔拉斯"],
        "安斯拉": ["伊库奇", "希尔塔蒙", "西卡塔"],
        "希尔塔蒙": ["安斯拉", "奥坎尼托", "伊库奇", "尤斯库仑", "新加达里"],
        "西卡塔": ["安斯拉", "奥马海仑", "欧图尼", "阿巴宗"],
        "欧图尼": ["西卡塔", "奥马海仑"],
        "奥马海仑": ["西卡塔", "欧图尼", "尤斯库仑"],
        "尤斯库仑": ["希尔塔蒙", "奥马海仑"],
        "奥坎尼托": ["希尔塔蒙"],
        "欧罗": ["乔萨密陀", "奥班伦", "伊什索蒙", "欧斯蒙"],
        "乔萨密陀": ["欧罗", "奥班伦", "列库里", "波耶伦", "新加达里"],
        "奥班伦": ["欧罗", "乔萨密陀", "波耶伦", "列库里"],
        "列库里": ["乔萨密陀", "奥班伦", "波耶伦"],
        "波耶伦": ["乔萨密陀", "奥班伦", "列库里", "诺玛尔"],
        "阿图莱玛": ["伊塔莫", "玛提斯塔"],
        "基尔玛贝": ["伊塔莫"],
        "瓦安卡伦": ["伊塔莫"],
        "玛提斯塔": ["阿图莱玛", "密茨伦"],
        "贾塔特": ["伊塔莫", "密茨伦"],
        "密茨伦": ["贾塔特", "玛提斯塔"],
        "伊塔莫": ["阿图莱玛", "基尔玛贝", "瓦安卡伦", "贾塔特", "玛乌纳斯"],
        "乌伊特里拉": ["乌恩帕斯", "诺玛尔"],
        "诺玛尔": ["乌伊特里拉", "什胡肯", "基尔拉斯", "赛西奥", "波耶伦"],
        "什胡肯": ["乌恩帕斯", "图乌瑞纳"],
        "图乌瑞纳": ["什胡肯", "基尔拉斯", "希尔瑟讷"],
        "希尔瑟讷": ["图乌瑞纳", "基尔拉斯", "伊纳洛", "伊卡密"],
        "基尔拉斯": ["诺玛尔", "图乌瑞纳", "希尔瑟讷"],
        "哈比伦": ["胡尔托肯", "贾卡纳尔维", "伊卡密"],
        "欧约伦": ["格昆塔米", "瓦托伦"],
        "胡尔托肯": ["哈比伦", "埃巴加瓦"],
        "格昆塔米": ["欧约伦", "贾卡纳尔维"],
        "贾卡纳尔维": ["哈比伦", "格昆塔米", "埃巴加瓦", "赛西奥"],
        "埃巴加瓦": ["胡尔托肯", "贾卡纳尔维", "赛西奥"],
        "赛西奥": ["埃巴加瓦", "贾卡纳尔维", "诺玛尔"],
        "马伊拉": ["爱科拉"],
        "米瑟约亚": ["爱科拉", "莱伊森", "塔瑟提"],
        "爱科拉": ["马伊拉", "米瑟约亚", "普尔乔拉", "莱伊森", "欧加仑"],
        "普尔乔拉": ["马伊拉", "爱科拉", "莱伊森", "伊卡密"],
        "莱伊森": ["爱科拉", "米瑟约亚", "普尔乔拉", "伊卡密"],
        "伊卡密": ["普尔乔拉", "莱伊森", "希尔瑟讷", "哈比伦"],
        "斯勒恩": ["索什恩"],
        "埃吉伦": ["索什恩", "温努斯", "瓦托伦", "恒托加拉"],
        "乌卡伦": ["科伊卡肯", "温努斯"],
        "科伊卡肯": ["乌卡伦", "温努斯"],
        "索什恩": ["斯勒恩", "埃吉伦", "瓦托伦"],
        "温努斯": ["埃吉伦", "乌卡伦", "科伊卡肯", "瓦托伦"],
        "瓦托伦": ["埃吉伦", "索什恩", "温努斯", "欧约伦"],
        "伊什索蒙": ["艾尔米亚", "萨基凯伦", "欧罗"],
        "艾尔米亚": ["伊什索蒙", "萨基凯伦", "弗瑞吉"],
        "萨基凯伦": ["伊什索蒙", "艾尔米亚", "弗瑞吉", "瓦胡诺米"],
        "弗瑞吉": ["艾尔米亚", "萨基凯伦", "以哈坎拿", "欧提托"],
        "以哈坎拿": ["弗瑞吉", "欧提托", "欧塔迈伦", "欧特色拉"],
        "瓦胡诺米": ["萨基凯伦"],
        "欧提托": ["弗瑞吉", "以哈坎拿"],
        "欧塔迈伦": ["以哈坎拿"],
        "欧斯蒙": ["库尔斯基", "因纳亚", "欧罗"],
        "库尔斯基": ["欧斯蒙", "鲁肯", "艾拉肯"],
        "因纳亚": ["欧斯蒙", "乌欧斯", "乌米纳斯"],
        "鲁肯": ["库尔斯基"],
        "乌米纳斯": ["因纳亚"],
        "艾拉肯": ["库尔斯基", "欧加仑"],
        "欧加仑": ["艾拉肯", "爱科拉", "BWF-ZZ"],
        "乌欧斯": ["因纳亚"],
        "埃加奥": ["帕拉", "EOA-ZC", "托蒂弗伦"],
        "夫斯库仑": ["尤蒙", "欧法戈"],
        "帕拉": ["埃加奥", "尤蒙", "LXQ2-T"],
        "尤蒙": ["夫斯库仑", "帕拉", "奥塔希拉"],
        "奥塔希拉": ["尤蒙", "塔瑟提", "埃加奥"],
        "塔瑟提": ["奥塔希拉", "埃加奥", "米瑟约亚"],
        "欧特色拉": ["瓦萨拉", "瓦尔瓦林", "恒托加拉", "吉安提", "以哈坎拿"],
        "沃斯基奥": ["瓦萨拉", "瓦尔瓦林", "乌查什"],
        "瓦尔瓦林": ["欧特色拉", "瓦萨拉", "吉安提"],
        "瓦萨拉": ["欧特色拉", "瓦尔瓦林", "吉安提", "沃斯基奥"],
        "吉安提": ["欧特色拉", "瓦萨拉", "瓦尔瓦林", "恒托加拉"],
        "恒托加拉": ["欧特色拉", "吉安提", "埃吉伦"],
        "奥斯阿": ["欧贝", "欧库仑", "马斯塔克蒙", "伊卢卡"],
        "欧贝": ["奥斯阿", "欧库仑", "马斯塔克蒙", "P3EN-E", "哈克农"],
        "欧库仑": ["奥斯阿", "欧贝", "马斯塔克蒙"],
        "伊卢卡": ["奥斯阿", "马斯塔克蒙", "乌查什"],
        "马斯塔克蒙": ["奥斯阿", "欧贝", "欧库仑", "伊卢卡", "乌查什"],
        "乌查什": ["伊卢卡", "马斯塔克蒙", "恒托加拉", "沃斯基奥"],
        "伊恩-奥斯塔": ["皮尔米特"],
        "阿里卡拉": ["新加达里"],
        "姆沃莱伦": ["吉他", "玛乌纳斯"],
        "希尔帕拉": ["乌尔仑"],
        "库索蒙莫": ["乌尔仑"],
        "吞塔拉斯": ["伊库奇"],
        "索巴色基": ["吉他"],
        "莫卡冷": ["新加达里"],
        "阿巴宗": ["西卡塔"],
        "伊纳洛": ["希尔瑟讷"],
        "哈克农": ["欧贝"],
        "托蒂弗伦": ["埃加奥"],
        "欧法戈": ["夫斯库仑"],
        "P3EN-E": ["欧贝"],
        "EOA-ZC": ["埃加奥"],
        "BWF-ZZ": ["欧加仑"],
        "LXQ2-T": ["帕拉"],
    }
    
    NPC_STATIONS = {
        "新加达里", "皮尔米特", "尼亚拜伦", "吉他", "基索加", "玛乌纳斯", "乌尔仑",
        "安斯拉", "希尔塔蒙", "西卡塔", "欧图尼", "奥马海仑", "尤斯库仑", "伊库奇", "奥坎尼托",
        "欧罗", "乔萨密陀", "奥班伦", "列库里", "波耶伦",
        "阿图莱玛", "基尔玛贝", "瓦安卡伦", "玛提斯塔", "贾塔特", "密茨伦", "伊塔莫",
        "乌伊特里拉", "诺玛尔", "什胡肯", "乌恩帕斯", "图乌瑞纳", "希尔瑟讷", "基尔拉斯",
        "哈比伦", "欧约伦", "胡尔托肯", "格昆塔米", "贾卡纳尔维", "埃巴加瓦", "赛西奥",
        "马伊拉", "米瑟约亚", "爱科拉", "普尔乔拉", "莱伊森", "伊卡密",
        "斯勒恩", "埃吉伦", "乌卡伦", "科伊卡肯", "索什恩", "温努斯", "瓦托伦",
        "伊什索蒙", "艾尔米亚", "萨基凯伦", "弗瑞吉", "以哈坎拿", "瓦胡诺米", "欧提托", "欧塔迈伦",
        "欧斯蒙", "库尔斯基", "因纳亚", "鲁肯", "乌米纳斯", "艾拉肯", "欧加仑", "乌欧斯",
        "埃加奥", "夫斯库仑", "帕拉", "尤蒙", "奥塔希拉", "塔瑟提",
        "欧特色拉", "沃斯基奥", "瓦尔瓦林", "瓦萨拉", "吉安提", "恒托加拉",
        "奥斯阿", "欧贝", "欧库仑", "伊卢卡", "马斯塔克蒙", "乌查什",
        "伊恩-奥斯塔", "阿里卡拉", "姆沃莱伦", "希尔帕拉", "库索蒙莫",
        "吞塔拉斯", "索巴色基", "莫卡冷", "阿巴宗", "伊纳洛",
        "哈克农", "托蒂弗伦", "欧法戈"
    }
    
    MARKET_SYSTEM = "吉他"
    
    # ========== 原矿数据 ==========
    ORES_DATA = {
        "凡晶石": {"volume": 0.1, "security": "high", "yield": {"三钛合金": 4}},
        "灼烧岩": {"volume": 0.15, "security": "high", "yield": {"三钛合金": 1.5, "类晶体胶矿": 1.1}},
        "干焦岩": {"volume": 0.3, "security": "high", "yield": {"类晶体胶矿": 0.9, "类银超金属": 0.3}},
        "斜长岩": {"volume": 0.35, "security": "high", "yield": {"三钛合金": 1.75, "类银超金属": 0.7}},
        "奥贝尔石": {"volume": 0.6, "security": "low", "yield": {"类晶体胶矿": 0.9, "同位聚合体": 0.75}},
        "水硼砂": {"volume": 1.2, "security": "low", "yield": {"类银超金属": 0.6, "同位聚合体": 1.2}},
        "杰斯贝矿": {"volume": 2.0, "security": "low", "yield": {"类银超金属": 1.5, "超新星诺克石": 0.5}},
        "同位原矿": {"volume": 3.0, "security": "low", "yield": {"类晶体胶矿": 4.5, "超新星诺克石": 1.2}},
        "希莫非特": {"volume": 3.0, "security": "low", "yield": {"同位聚合体": 2.4, "超新星诺克石": 0.9}},
        "片麻岩": {"volume": 5.0, "security": "low", "yield": {"类晶体胶矿": 20, "类银超金属": 15, "同位聚合体": 8}},
        "黑赭石": {"volume": 8.0, "security": "null", "yield": {"类银超金属": 13.6, "同位聚合体": 12, "超新星诺克石": 3.2}},
        "灰岩": {"volume": 16.0, "security": "null", "yield": {"三钛合金": 480, "同位聚合体": 10, "晶状石英核岩": 0.8, "超新星诺克石": 1.6, "超噬矿": 0.4}},
        "艾克诺岩": {"volume": 16.0, "security": "null", "yield": {"类晶体胶矿": 32, "类银超金属": 12, "超噬矿": 1.2}},
        "双多特石": {"volume": 16.0, "security": "null", "yield": {"类晶体胶矿": 32, "类银超金属": 12, "晶状石英核岩": 1.6}},
        "克洛基石": {"volume": 16.0, "security": "null", "yield": {"类晶体胶矿": 8, "类银超金属": 20, "超新星诺克石": 8}},
        "基腹断岩": {"volume": 40.0, "security": "null", "yield": {"莫尔石": 1.4}},
    }
    
    MINERAL_VOLUME = 0.01
    
    # ========== 制造系统 ==========
    MANUFACTURING_RECIPES = {
        "小鹰级": {"三钛合金": 32000, "类晶体胶矿": 6000, "类银超金属": 2500, "同位聚合体": 500},
        "冲锋者级": {"三钛合金": 22400, "类晶体胶矿": 4200, "类银超金属": 1750, "同位聚合体": 350},
        "海燕级": {"三钛合金": 80000, "类晶体胶矿": 15000, "类银超金属": 5000, "同位聚合体": 1000},
        "狐鼬级": {"三钛合金": 80000, "类晶体胶矿": 15000, "类银超金属": 3750, "同位聚合体": 2000, "超新星诺克石": 750, "晶状石英核岩": 125, "超噬矿": 70},
        "巨鸟级": {"三钛合金": 540000, "类晶体胶矿": 180000, "类银超金属": 36000, "同位聚合体": 10000, "超新星诺克石": 1500, "晶状石英核岩": 350, "超噬矿": 140},
        "回旋者级": {"三钛合金": 1600000, "类晶体胶矿": 300000, "类银超金属": 75000, "同位聚合体": 40000, "超新星诺克石": 15000, "晶状石英核岩": 2500, "超噬矿": 1400},
        "娜迦级": {"三钛合金": 3640000, "类晶体胶矿": 1300000, "类银超金属": 234000, "同位聚合体": 26000, "超新星诺克石": 10400, "晶状石英核岩": 2600, "超噬矿": 520},
        "鹏鲲级": {"三钛合金": 5200000, "类晶体胶矿": 2600000, "类银超金属": 390000, "同位聚合体": 130000, "超新星诺克石": 15600, "晶状石英核岩": 3900, "超噬矿": 1950},
        "渡神级": {"三钛合金": 2715550, "类晶体胶矿": 9770049, "类银超金属": 2716701, "同位聚合体": 755166.75, "超新星诺克石": 76812.67, "晶状石英核岩": 38179.69, "超噬矿": 19251.6},
    }

    MANUFACTURING_TIME = {
        "小鹰级": 3264, "冲锋者级": 3264, "海燕级": 4860, "狐鼬级": 6480,
        "巨鸟级": 6480, "回旋者级": 6480, "娜迦级": 8160, "鹏鲲级": 9780, "渡神级": 816000,
    }

    # ========== 刷怪系统 ==========
    # 怪物属性（单只）- 古斯塔斯海盗
    RAT_DATA = {
        1: {"hp": 366480, "dps": 5, "bounty": 220000, "name": "古斯塔斯藏身处", "ship": "小鹰级"},
        2: {"hp": 366480, "dps": 5, "bounty": 435000, "name": "古斯塔斯洞穴", "ship": "小鹰级"},
        3: {"hp": 608400, "dps": 7, "bounty": 1100000, "name": "古斯塔斯庇护所", "ship": "海燕级"},
        4: {"hp": 608400, "dps": 7, "bounty": 1450000, "name": "古斯塔斯贼窝", "ship": "海燕级"},
        5: {"hp": 929400, "dps": 33, "bounty": 2800000, "name": "古斯塔斯船坞", "ship": "巨鸟级"},
        6: {"hp": 929400, "dps": 33, "bounty": 3350000, "name": "古斯塔斯集会点", "ship": "巨鸟级"},
        7: {"hp": 1727280, "dps": 36, "bounty": 7200000, "name": "古斯塔斯附属区", "ship": "娜迦级"},
        8: {"hp": 1727280, "dps": 36, "bounty": 8500000, "name": "古斯塔斯基地", "ship": "娜迦级"},
        9: {"hp": 1686840, "dps": 95, "bounty": 10000000, "name": "古斯塔斯堡垒", "ship": "鹏鲲级"},
    }

    # 维修延时（往返时间）- 秒 - 作战舰船刷怪用
    REPAIR_DELAY = {
        "小鹰级": 38,
        "海燕级": 41.4,
        "巨鸟级": 45,
        "娜迦级": 51.2,
        "鹏鲲级": 66,
    }

    # 放矿延时（往返时间）- 秒 - 采矿船挖矿用
    MINING_DELAY = {
        "冲锋者级": 40,  # 起跳4s + 30AU/5AU/s + 进出站10s = 20s单程, 往返40s
        "回旋者级": 64,  # 起跳12s + 30AU/3AU/s + 进出站10s = 32s单程, 往返64s
    }

    # 根据星系安全等级获取刷怪等级
    def get_rat_level_by_security(self, security: float) -> list:
        """根据安全等级返回对应的刷怪等级列表"""
        if security >= 0.9:
            return [1]
        elif security >= 0.8:
            return [1]
        elif security >= 0.7:
            return [2]
        elif security >= 0.6:
            return [2]
        elif security >= 0.5:
            return [3]
        elif security >= 0.4:
            return [3]
        elif security >= 0.3:
            return [4]
        elif security >= 0.2:
            return [4]
        elif security >= 0.1:
            return [5]
        elif security > 0.0:
            return [5]
        elif security >= -0.1:
            return [6]
        elif security >= -0.2:
            return [6]
        elif security >= -0.3:
            return [7]
        elif security >= -0.4:
            return [7]
        elif security >= -0.5:
            return [8]
        elif security >= -0.6:
            return [8]
        elif security >= -0.7:
            return [8]
        elif security >= -0.8:
            return [9]
        elif security >= -0.9:
            return [9]
        else:
            return [9]

    # ========== 基础指令 ==========
    @filter.command("游戏帮助")
    async def game_help(self, event: AstrMessageEvent):
        """显示帮助信息"""
        try:
            logger.info(f"用户 {event.get_sender_id()} 请求帮助")
            help_text = """🚀 星际黎明 - 太空挂机游戏

📋 基础功能：
/游戏注册 - 创建游戏角色
/游戏注销 - 注销当前角色
/游戏帮助 - 显示所有可用指令
/游戏状态 - 查看飞行员状态、位置、舰船、当前活动

💰 资产功能：
/游戏资产 - 查看有资产的星系名称（包括舰船和材料）
/游戏仓库 - 查看当前星系仓库中的材料
/游戏仓库 <星系名称> - 查看该星系的材料
/游戏机库 - 查看当前星系机库中的舰船
/游戏机库 <星系名称> - 查看该星系的舰船
/游戏钱包 - 查看当前钱包余额

📦 运输功能：
/游戏货柜 - 查看当前驾驶的船的货柜和矿舱
/游戏装载 - 装载机库全部物品（矿石优先装入矿舱）
/游戏装载 <物品名> - 该物品全装（自动检查超载）
/游戏装载 <物品名> <数量> - 该物品装载指定数量
/游戏卸载 - 卸载所有货物
/游戏卸载 <物品名> - 该物品全卸载
/游戏卸载 <物品名> <数量> - 该物品卸载指定数量
/游戏运输 <起始星系> <目标星系> - 自动在两个星系之间运输物品
/游戏运输状态 - 查看运输任务状态
/游戏停止运输 - 停止运输任务

🌌 星系导航系统：
/游戏星系 - 查看当前星系的小行星带和刷怪点
/游戏星图 - 查看所有星域列表
/游戏星图 <星域名称> - 查看该星域的所有星座列表
/游戏星图 <星座名称> - 查看该星座的所有星系列表
/游戏星图 <星系名称> - 查看该星系的星门连接
/游戏导航 <目标星系> - 自动规划路线并导航
/游戏导航状态 - 查看导航进度，到哪个星系了
/游戏停止导航 - 停止当前导航

⛏️ 挖矿系统：
/游戏挖矿 - 在当前星系小行星带挖矿
/游戏停止挖矿 - 停止挖矿并返回空间站

💡 挖矿说明：
• 高安/低安区：矿石直接存入本地空间站
• 00区：矿舱满后需导航至最近NPC空间站卸货，会增加往返导航时间

👾 刷怪系统：
/游戏刷怪 - 在当前星系开始刷怪（自动根据舰船选择合适等级）
/游戏停止刷怪 - 停止刷怪并结算收益

🔥 精炼系统：
/游戏矿石 - 查看所有原矿列表
/游戏精炼 - 精炼当前空间站中所有原矿
/游戏精炼 <原矿名> - 精炼指定原矿的所有数量
/游戏精炼 <原矿名> <数量> - 精炼指定原矿的指定数量
/游戏提炼表 <原矿名> - 查看该原矿提炼产出表

🔧 制造系统：
/游戏制造 <舰船> - 查看该舰船的需求矿物和制造时间
/游戏制造 <舰船> <数量> - 消耗矿物制造舰船
/游戏制造状态 - 查看制造进度

🚀 舰船系统：
/游戏舰船 - 查看所有舰船列表
/游戏舰船 <舰船> - 查看该舰船属性
/游戏换船 <舰船名称> - 更换当前驾驶的舰船（需要在空间站中）

💰 市场系统（仅吉他）：
/游戏市场 <物品名> - 查看该物品的最低价卖单和最高价买单（前5个）
/游戏卖单 <物品名> <数量> <单价> - 上架卖单
/游戏买单 <物品名> <数量> <单价> - 上架买单
/游戏我的订单 - 查看自己上架的订单
/游戏取消订单 <订单ID> - 取消指定订单
/游戏购买 <物品名> [数量] - 自动购买该物品的最低价卖单

输入 /游戏注册 开始游戏！"""
            yield event.plain_result(help_text)
            logger.info("帮助信息已发送")
        except Exception as e:
            logger.error(f"显示帮助时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            yield event.plain_result(f"❌ 显示帮助失败: {str(e)}")

    @filter.command("游戏注册")
    async def register_player(self, event: AstrMessageEvent):
        """注册游戏角色"""
        try:
            user_id = str(event.get_sender_id())
            user_name = event.get_sender_name()
            logger.info(f"用户 {user_name}({user_id}) 正在注册游戏")

            if user_id in self.players:
                yield event.plain_result(f"👋 欢迎回来，飞行员 {user_name}！\n输入 /游戏状态 查看当前状态")
            else:
                player = self.get_player(user_id)
                player['name'] = user_name
                self.save_players()
                yield event.plain_result(f"🎉 欢迎加入星际黎明，飞行员 {user_name}！\n\n📍 出生点：吉他\n🚀 初始舰船：冲锋者级\n\n输入 /游戏帮助 查看所有指令")
        except Exception as e:
            logger.error(f"注册游戏时出错: {e}")
            yield event.plain_result(f"❌ 注册失败: {str(e)}")

    @filter.command("游戏注销")
    async def unregister_player(self, event: AstrMessageEvent):
        """注销当前角色"""
        try:
            user_id = str(event.get_sender_id())
            logger.info(f"用户 {user_id} 请求注销角色")

            if user_id not in self.players:
                yield event.plain_result("❌ 您还没有注册游戏角色")
                return

            # 删除玩家数据
            del self.players[user_id]
            self.save_players()
            yield event.plain_result("✅ 角色已注销，您可以重新注册新角色\n输入 /游戏注册 创建新角色")
            logger.info(f"用户 {user_id} 角色已注销")
        except Exception as e:
            logger.error(f"注销角色时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            yield event.plain_result(f"❌ 注销失败: {str(e)}")

    @filter.command("游戏状态")
    async def player_status(self, event: AstrMessageEvent):
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)

        # 结算各种状态（先结算，确保位置信息是最新的）
        nav_result = self.settle_navigation(player)
        mfg_result = self.settle_manufacturing(player)
        
        # 如果有结算结果，保存数据
        if nav_result or mfg_result:
            self.save_players()

        ship = self.get_player_ship(player)
        ship_name = ship['name'] if ship else "无"
        
        # 获取当前位置（结算后）
        current_location = player['location']
        security = self.get_system_security(current_location)

        status_text = f"""📊 飞行员状态

👤 名称：{player['name']}
📍 位置：{current_location} [{security}]
🚀 舰船：{ship_name}
💰 钱包：¥{player['wallet']:,}
📊 状态：{player['status']}"""

        if nav_result:
            status_text += f"\n\n{nav_result}"
        if mfg_result:
            status_text += f"\n\n{mfg_result}"

        if player['mining']:
            mining = player['mining']
            duration = time.time() - mining['start_time']
            status_text += f"\n\n⛏️ 挖矿中...\n  地点：{mining['system']}小行星带\n  已进行：{duration/60:.1f}分钟"

        if player.get('ratting'):
            ratting = player['ratting']
            duration = time.time() - ratting['start_time']
            status_text += f"\n\n👾 刷怪中...\n  地点：{ratting['system']} {self.RAT_DATA[ratting['level']]['name']}\n  已进行：{duration/60:.1f}分钟"

        if player.get('navigating'):
            nav = player['navigating']
            status_text += f"\n\n🚀 导航中...\n  {nav['current']} → {nav['target']}\n  进度：{nav['current_step']}/{nav['total_steps']} 跳"

        if player.get('manufacturing'):
            mfg = player['manufacturing']
            elapsed = time.time() - mfg['start_time']
            remaining = max(0, mfg['duration'] - elapsed)
            progress = min(100, elapsed / mfg['duration'] * 100)
            status_text += f"\n\n🔧 制造中：{mfg['ship']}\n  进度：{progress:.1f}%\n  剩余：{remaining/60:.1f}分钟"
        
        yield event.plain_result(status_text)

    # ========== 资产功能 ==========
    @filter.command("游戏钱包")
    async def check_wallet(self, event: AstrMessageEvent):
        """查看钱包余额"""
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        yield event.plain_result(f"💰 钱包余额：¥{player['wallet']:,}")

    @filter.command("游戏仓库")
    async def check_warehouse(self, event: AstrMessageEvent):
        """查看仓库材料"""
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        args = event.message_str.split()[1:]
        
        # 确定要查看的星系
        if len(args) >= 1:
            system = args[0]
            if system not in self.SYSTEM_SECURITY and system not in self.GATE_CONNECTIONS:
                yield event.plain_result(f"❌ 未知星系：{system}")
                return
        else:
            system = player['location'].replace('小行星带', '')
        
        if system not in player['assets']:
            yield event.plain_result(f"📦 {system} 机库\n\n暂无材料")
            return
        
        assets = player['assets'][system]
        
        text = f"📦 {system} 仓库\n\n"

        # 原矿
        ores = assets.get('ores', {})
        if ores:
            text += "⛏️ 原矿：\n"
            for name, amount in sorted(ores.items()):
                text += f"  {name}：{amount:.2f}单位\n"
        else:
            text += "⛏️ 原矿：无\n"

        # 矿物
        minerals = assets.get('minerals', {})
        if minerals:
            text += "\n💎 矿物：\n"
            for name, amount in sorted(minerals.items()):
                text += f"  {name}：{amount:.2f}单位\n"
        else:
            text += "\n💎 矿物：无\n"

        yield event.plain_result(text)

    @filter.command("游戏资产")
    async def check_assets(self, event: AstrMessageEvent):
        """查看有资产的星系"""
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        # 结算各种状态
        nav_result = self.settle_navigation(player)
        mfg_result = self.settle_manufacturing(player)
        
        # 如果有结算结果，保存数据
        if nav_result or mfg_result:
            self.save_players()
        
        text = f"📦 资产总览\n\n💰 钱包：¥{player['wallet']:,}\n"
        
        if nav_result:
            text += f"\n🚀 {nav_result}\n"
        if mfg_result:
            text += f"\n🔧 {mfg_result}\n"
        
        # 获取所有有资产的星系
        systems_with_assets = []
        for system, assets in player['assets'].items():
            has_ships = len(assets.get('ships', [])) > 0
            has_ores = len(assets.get('ores', {})) > 0
            has_minerals = len(assets.get('minerals', {})) > 0
            if has_ships or has_ores or has_minerals:
                systems_with_assets.append(system)
        
        if systems_with_assets:
            text += f"\n📍 有资产的星系：\n"
            for system in sorted(systems_with_assets):
                assets = player['assets'][system]
                ships_count = len(assets.get('ships', []))
                ores_count = len(assets.get('ores', {}))
                minerals_count = len(assets.get('minerals', {}))
                info = []
                if ships_count > 0:
                    info.append(f"{ships_count}艘舰船")
                if ores_count > 0:
                    info.append(f"{ores_count}种原矿")
                if minerals_count > 0:
                    info.append(f"{minerals_count}种矿物")
                text += f"  {system} - {', '.join(info)}\n"
        else:
            text += "\n📍 暂无资产\n"
        
        text += "\n使用 /游戏仓库 <星系> 查看详细材料"
        yield event.plain_result(text)

    def _get_cargo_volume(self, cargo: Dict) -> float:
        """计算货柜当前使用体积"""
        total_volume = 0
        for item_type, items in cargo.items():
            if item_type == '舰船':
                # 使用每艘舰船的实际体积
                for ship_data in items:
                    ship_name = ship_data['name']
                    ship_volume = self.SHIPS_DATA.get(ship_name, {}).get('volume', 1000)
                    total_volume += ship_volume
            else:
                for item_name, amount in items.items():
                    if item_type == '矿石':
                        ore_data = self.ORES_DATA.get(item_name, {})
                        item_volume = ore_data.get('volume', 0.1)
                    elif item_type == '矿物':
                        item_volume = 0.01
                    else:
                        item_volume = 0.1
                    total_volume += amount * item_volume
        return total_volume

    def _get_item_volume(self, item_type: str, item_name: str) -> float:
        """获取单个物品的体积"""
        if item_type == '矿石':
            ore_data = self.ORES_DATA.get(item_name, {})
            return ore_data.get('volume', 0.1)
        elif item_type == '矿物':
            return 0.01
        elif item_type == '舰船':
            # 从舰船数据获取实际体积
            return self.SHIPS_DATA.get(item_name, {}).get('volume', 1000)
        return 0.1

    @filter.command("游戏装载")
    async def load_cargo(self, event: AstrMessageEvent):
        """将空间站货物装载到舰船货柜/矿舱"""
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)

        args = event.message_str.split()[1:]

        # 检查状态
        if player['status'] != '待机':
            yield event.plain_result(f"❌ 当前状态为{player['status']}，无法装载货物")
            return

        # 获取当前舰船
        ship = self.get_player_ship(player)
        if not ship:
            yield event.plain_result("❌ 没有驾驶舰船")
            return

        ship_name = ship['name']
        ship_data = self.SHIPS_DATA.get(ship_name, {})
        cargo_capacity = ship_data.get('cargo', 0)
        ore_hold_capacity = ship_data.get('ore_hold', 0)  # 矿舱容量

        # 检查舰船是否有货柜或矿舱
        if cargo_capacity <= 0 and ore_hold_capacity <= 0:
            yield event.plain_result(f"❌ {ship_name} 没有货柜或矿舱，无法装载货物")
            return

        # 获取当前星系资产
        system = player['location'].replace('小行星带', '')
        assets = player['assets'].get(system, {})

        # 初始化货柜和矿舱
        if 'cargo' not in ship:
            ship['cargo'] = {}
        if 'ore_hold' not in ship:
            ship['ore_hold'] = {}

        # 计算当前货柜和矿舱使用
        current_cargo_volume = self._get_cargo_volume(ship.get('cargo', {}))
        current_ore_hold_volume = self._get_cargo_volume(ship.get('ore_hold', {}))
        available_cargo_space = cargo_capacity - current_cargo_volume
        available_ore_hold_space = ore_hold_capacity - current_ore_hold_volume

        # 无参数 - 装载机库全部物品
        if len(args) == 0:
            loaded_items = []

            # 装载矿石（优先装入矿舱，矿舱满了再装货柜）
            for ore_name, ore_amount in list(assets.get('ores', {}).items()):
                item_volume = self._get_item_volume('矿石', ore_name)
                remaining_amount = ore_amount

                # 先尝试装入矿舱
                if available_ore_hold_space > 0 and ore_hold_capacity > 0:
                    max_load_ore_hold = int(available_ore_hold_space / item_volume)
                    load_amount_ore_hold = min(remaining_amount, max_load_ore_hold)

                    if load_amount_ore_hold > 0:
                        # 从仓库扣除
                        assets['ores'][ore_name] -= load_amount_ore_hold
                        if assets['ores'][ore_name] <= 0:
                            del assets['ores'][ore_name]

                        # 装入矿舱
                        if ore_name not in ship['ore_hold']:
                            ship['ore_hold'][ore_name] = 0
                        ship['ore_hold'][ore_name] += load_amount_ore_hold

                        loaded_volume = load_amount_ore_hold * item_volume
                        available_ore_hold_space -= loaded_volume
                        remaining_amount -= load_amount_ore_hold
                        loaded_items.append(f"⛏️ {ore_name} × {load_amount_ore_hold} (矿舱)")

                # 剩余的装入货柜
                if remaining_amount > 0 and available_cargo_space > 0:
                    max_load_cargo = int(available_cargo_space / item_volume)
                    load_amount_cargo = min(remaining_amount, max_load_cargo)

                    if load_amount_cargo > 0:
                        # 从仓库扣除（如果矿舱部分没有扣完）
                        if ore_name in assets.get('ores', {}):
                            assets['ores'][ore_name] -= load_amount_cargo
                            if assets['ores'][ore_name] <= 0:
                                del assets['ores'][ore_name]

                        # 装入货柜
                        if '矿石' not in ship['cargo']:
                            ship['cargo']['矿石'] = {}
                        if ore_name not in ship['cargo']['矿石']:
                            ship['cargo']['矿石'][ore_name] = 0
                        ship['cargo']['矿石'][ore_name] += load_amount_cargo

                        loaded_volume = load_amount_cargo * item_volume
                        available_cargo_space -= loaded_volume
                        loaded_items.append(f"⛏️ {ore_name} × {load_amount_cargo} (货柜)")

            # 装载矿物（只能装入货柜）
            for mineral_name, mineral_amount in list(assets.get('minerals', {}).items()):
                item_volume = 0.01
                max_load = int(available_cargo_space / item_volume)

                if max_load <= 0:
                    break

                load_amount = min(mineral_amount, max_load)
                if load_amount > 0:
                    # 从仓库扣除
                    assets['minerals'][mineral_name] -= load_amount
                    if assets['minerals'][mineral_name] <= 0:
                        del assets['minerals'][mineral_name]

                    # 装载到货柜
                    if '矿物' not in ship['cargo']:
                        ship['cargo']['矿物'] = {}
                    if mineral_name not in ship['cargo']['矿物']:
                        ship['cargo']['矿物'][mineral_name] = 0
                    ship['cargo']['矿物'][mineral_name] += load_amount

                    loaded_volume = load_amount * item_volume
                    available_cargo_space -= loaded_volume
                    loaded_items.append(f"💎 {mineral_name} × {load_amount}")

            # 装载舰船（检查货柜是否为空）
            for target_ship in list(assets.get('ships', [])):
                if target_ship['id'] == player.get('ship_id'):
                    continue

                # 检查被装载舰船的货柜是否为空
                target_cargo = target_ship.get('cargo', {})
                if target_cargo and self._get_cargo_volume(target_cargo) > 0:
                    continue  # 跳过货柜有东西的舰船

                # 获取舰船实际体积
                target_ship_name = target_ship['name']
                item_volume = self.SHIPS_DATA.get(target_ship_name, {}).get('volume', 1000)

                if available_cargo_space < item_volume:
                    break

                # 从仓库扣除
                assets['ships'].remove(target_ship)

                # 装载到货柜
                if '舰船' not in ship['cargo']:
                    ship['cargo']['舰船'] = []
                ship['cargo']['舰船'].append(target_ship)

                available_cargo_space -= item_volume
                # 货柜有东西的显示ID，否则只显示名称（后续统计数量）
                target_cargo_check = target_ship.get('cargo', {})
                if target_cargo_check and self._get_cargo_volume(target_cargo_check) > 0:
                    loaded_items.append(f"🚀 {target_ship['name']} (ID:{target_ship['id']})")
                else:
                    loaded_items.append(f"🚀 {target_ship['name']}")

            self.save_players()

            if not loaded_items:
                yield event.plain_result("❌ 机库为空或货柜已满")
                return

            new_volume = self._get_cargo_volume(ship.get('cargo', {}))
            # 区分有ID的舰船（货柜有东西）和没ID的舰船（货柜为空）
            loaded_ships_empty = {}  # 货柜为空的舰船统计
            loaded_ships_with_id = []  # 货柜有东西的舰船（带ID）
            other_items = []
            for item in loaded_items:
                if item.startswith('🚀'):
                    if '(ID:' in item:
                        loaded_ships_with_id.append(item)
                    else:
                        # 提取舰船名称
                        ship_name = item.replace('🚀 ', '')
                        loaded_ships_empty[ship_name] = loaded_ships_empty.get(ship_name, 0) + 1
                else:
                    other_items.append(item)

            # 检查是否有剩余物品未装载
            remaining_items = []
            for ore_name, ore_amount in assets.get('ores', {}).items():
                remaining_items.append(f"⛏️ {ore_name} × {ore_amount}")
            for mineral_name, mineral_amount in assets.get('minerals', {}).items():
                remaining_items.append(f"💎 {mineral_name} × {mineral_amount}")
            # 统计剩余舰船：货柜有东西的显示ID，空的只统计数量
            remaining_ships_empty = {}  # 货柜为空的舰船统计
            remaining_ships_with_cargo = []  # 货柜有东西的舰船列表
            for s in assets.get('ships', []):
                if s['id'] != player.get('ship_id'):
                    ship_cargo = s.get('cargo', {})
                    if ship_cargo and self._get_cargo_volume(ship_cargo) > 0:
                        # 货柜有东西，显示ID
                        remaining_ships_with_cargo.append(f"🚀 {s['name']} (ID:{s['id']})")
                    else:
                        # 货柜为空，统计数量
                        ship_name = s['name']
                        remaining_ships_empty[ship_name] = remaining_ships_empty.get(ship_name, 0) + 1
            # 添加货柜为空的舰船统计
            for ship_name, count in remaining_ships_empty.items():
                remaining_items.append(f"🚀 {ship_name} × {count}")
            # 添加货柜有东西的舰船
            remaining_items.extend(remaining_ships_with_cargo)

            text = f"✅ 装载完成\n\n🚀 舰船：{ship_name}\n📦 货柜容量：{new_volume:.2f}/{cargo_capacity}m³\n\n"
            # 显示货柜为空的舰船统计
            for ship_name, count in loaded_ships_empty.items():
                text += f"🚀 {ship_name} × {count}\n"
            # 显示货柜有东西的舰船（带ID）
            for ship_item in loaded_ships_with_id:
                text += f"{ship_item}\n"
            if other_items:
                text += "装载物品：\n"
                text += "\n".join(other_items)

            if remaining_items:
                text += f"\n\n📦 以下物品因空间不足留在机库：\n"
                text += "\n".join(remaining_items[:5])  # 最多显示5项
                if len(remaining_items) > 5:
                    text += f"\n... 还有 {len(remaining_items) - 5} 项"

            yield event.plain_result(text)
            return

        # 有参数 - 装载指定物品
        item_name = args[0]
        amount = int(args[1]) if len(args) > 1 else None

        # 查找物品类型和数量
        item_type = None
        available = 0
        item_volume = 0

        if item_name in assets.get('ores', {}):
            item_type = '矿石'
            available = assets['ores'][item_name]
            item_volume = self._get_item_volume('矿石', item_name)
        elif item_name in assets.get('minerals', {}):
            item_type = '矿物'
            available = assets['minerals'][item_name]
            item_volume = 0.01
        else:
            # 检查是否是舰船
            for s in assets.get('ships', []):
                if s['name'] == item_name and s['id'] != player.get('ship_id'):
                    # 检查被装载舰船的货柜是否为空
                    target_cargo = s.get('cargo', {})
                    if target_cargo and self._get_cargo_volume(target_cargo) > 0:
                        yield event.plain_result(f"❌ {s['name']} (ID:{s['id']}) 货柜中有货物，无法装载")
                        return
                    item_type = '舰船'
                    available = 1
                    # 获取舰船实际体积
                    item_volume = self.SHIPS_DATA.get(item_name, {}).get('volume', 1000)
                    target_ship = s
                    break

        if not item_type:
            yield event.plain_result(f"❌ 机库中没有 {item_name}")
            return

        # 确定装载数量
        if amount is None or amount > available:
            amount = available

        # 矿石优先装入矿舱，矿舱满了再装货柜
        if item_type == '矿石' and ore_hold_capacity > 0:
            total_volume = amount * item_volume
            load_to_ore_hold = 0
            load_to_cargo = 0

            # 先尝试装入矿舱
            if available_ore_hold_space > 0:
                max_to_ore_hold = int(available_ore_hold_space / item_volume)
                load_to_ore_hold = min(amount, max_to_ore_hold)
                amount -= load_to_ore_hold

            # 剩余的装入货柜
            if amount > 0 and available_cargo_space > 0:
                max_to_cargo = int(available_cargo_space / item_volume)
                load_to_cargo = min(amount, max_to_cargo)
                amount -= load_to_cargo

            total_loaded = load_to_ore_hold + load_to_cargo

            if total_loaded <= 0:
                yield event.plain_result(f"❌ 矿舱和货柜都已满，无法装载")
                return

            # 从仓库扣除
            assets['ores'][item_name] -= total_loaded
            if assets['ores'][item_name] <= 0:
                del assets['ores'][item_name]

            # 装入矿舱
            if load_to_ore_hold > 0:
                if item_name not in ship['ore_hold']:
                    ship['ore_hold'][item_name] = 0
                ship['ore_hold'][item_name] += load_to_ore_hold

            # 装入货柜
            if load_to_cargo > 0:
                if '矿石' not in ship['cargo']:
                    ship['cargo']['矿石'] = {}
                if item_name not in ship['cargo']['矿石']:
                    ship['cargo']['矿石'][item_name] = 0
                ship['cargo']['矿石'][item_name] += load_to_cargo

            self.save_players()

            # 显示结果
            ore_hold_volume = self._get_cargo_volume(ship.get('ore_hold', {}))
            cargo_volume = self._get_cargo_volume(ship.get('cargo', {}))
            text = f"✅ 装载完成\n\n🚀 舰船：{ship_name}\n"
            if ore_hold_capacity > 0:
                text += f"⛏️ 矿舱容量：{ore_hold_volume:.2f}/{ore_hold_capacity}m³\n"
            text += f"📦 货柜容量：{cargo_volume:.2f}/{cargo_capacity}m³\n\n"
            if load_to_ore_hold > 0:
                text += f"⛏️ {item_name} × {load_to_ore_hold} (矿舱)\n"
            if load_to_cargo > 0:
                text += f"⛏️ {item_name} × {load_to_cargo} (货柜)\n"
            if amount > 0:
                text += f"\n⚠️ 还有 {amount} 单位因空间不足留在机库"

            yield event.plain_result(text)
            return

        # 矿物和舰船只能装入货柜
        total_volume = amount * item_volume
        if total_volume > available_cargo_space:
            # 计算能装多少
            max_amount = int(available_cargo_space / item_volume)
            if max_amount <= 0:
                yield event.plain_result(f"❌ 货柜已满，无法装载")
                return
            amount = min(amount, max_amount)
            total_volume = amount * item_volume

        # 从仓库扣除
        if item_type == '矿石':
            assets['ores'][item_name] -= amount
            if assets['ores'][item_name] <= 0:
                del assets['ores'][item_name]
        elif item_type == '矿物':
            assets['minerals'][item_name] -= amount
            if assets['minerals'][item_name] <= 0:
                del assets['minerals'][item_name]
        elif item_type == '舰船':
            assets['ships'].remove(target_ship)

        # 装载到货柜
        if item_type == '舰船':
            if '舰船' not in ship['cargo']:
                ship['cargo']['舰船'] = []
            ship['cargo']['舰船'].append(target_ship)
        else:
            if item_type not in ship['cargo']:
                ship['cargo'][item_type] = {}
            if item_name not in ship['cargo'][item_type]:
                ship['cargo'][item_type][item_name] = 0
            ship['cargo'][item_type][item_name] += amount

        self.save_players()

        new_volume = self._get_cargo_volume(ship.get('cargo', {}))
        text = f"✅ 装载完成\n\n🚀 舰船：{ship_name}\n📦 货柜容量：{new_volume:.2f}/{cargo_capacity}m³\n\n"
        if item_type == '舰船':
            text += f"🚀 {item_name} × 1"
        else:
            text += f"⛏️ {item_name} × {amount}"
        yield event.plain_result(text)

    @filter.command("游戏卸载")
    async def unload_cargo(self, event: AstrMessageEvent):
        """将舰船货柜/矿舱中的货物卸载到空间站"""
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)

        args = event.message_str.split()[1:]

        # 检查状态
        if player['status'] != '待机':
            yield event.plain_result(f"❌ 当前状态为{player['status']}，无法卸载货物")
            return

        # 获取当前舰船
        ship = self.get_player_ship(player)
        if not ship:
            yield event.plain_result("❌ 没有驾驶舰船")
            return

        ship_name = ship['name']
        cargo = ship.get('cargo', {})
        ore_hold = ship.get('ore_hold', {})

        if not cargo and not ore_hold:
            yield event.plain_result("❌ 舰船货柜和矿舱都为空")
            return

        # 获取当前星系
        system = player['location'].replace('小行星带', '')
        if system not in player['assets']:
            player['assets'][system] = {"minerals": {}, "ores": {}, "ships": []}
        assets = player['assets'][system]

        # 无参数 - 卸载所有货物
        if len(args) == 0:
            unloaded_items = []

            # 先卸载矿舱中的矿石
            for ore_name, amount in list(ore_hold.items()):
                if ore_name not in assets['ores']:
                    assets['ores'][ore_name] = 0
                assets['ores'][ore_name] += amount
                unloaded_items.append(f"⛏️ {ore_name} × {amount} (矿舱)")

            # 清空矿舱
            ship['ore_hold'] = {}

            # 卸载货柜中的货物
            for item_type, items in list(cargo.items()):
                if item_type == '舰船':
                    for ship_data in items:
                        assets['ships'].append(ship_data)
                        unloaded_items.append(f"🚀 {ship_data['name']}")
                else:
                    for item_name, amount in items.items():
                        if item_type == '矿石':
                            if item_name not in assets['ores']:
                                assets['ores'][item_name] = 0
                            assets['ores'][item_name] += amount
                        elif item_type == '矿物':
                            if item_name not in assets['minerals']:
                                assets['minerals'][item_name] = 0
                            assets['minerals'][item_name] += amount
                        unloaded_items.append(f"⛏️ {item_name} × {amount}")

            # 清空货柜
            ship['cargo'] = {}

            self.save_players()

            text = f"✅ 卸载完成\n\n🚀 舰船：{ship_name}\n📍 地点：{system}空间站\n\n卸载物品：\n"
            text += "\n".join(unloaded_items)
            yield event.plain_result(text)
            return

        # 有参数 - 卸载指定物品
        item_name = args[0]
        amount = int(args[1]) if len(args) > 1 else None

        # 先在矿舱中查找（矿石优先从矿舱卸载）
        if item_name in ore_hold:
            available = ore_hold[item_name]
            if amount is None or amount > available:
                amount = available

            # 卸载到仓库
            if item_name not in assets['ores']:
                assets['ores'][item_name] = 0
            assets['ores'][item_name] += amount

            # 从矿舱扣除
            ore_hold[item_name] -= amount
            if ore_hold[item_name] <= 0:
                del ore_hold[item_name]

            self.save_players()

            text = f"✅ 卸载完成\n\n🚀 舰船：{ship_name}\n📍 地点：{system}空间站\n\n"
            text += f"⛏️ {item_name} × {amount} (矿舱)\n"
            yield event.plain_result(text)
            return

        # 在货柜中查找
        item_type = None
        available = 0

        for cargo_type, items in cargo.items():
            if cargo_type == '舰船':
                for idx, ship_data in enumerate(items):
                    if ship_data['name'] == item_name:
                        item_type = '舰船'
                        available = 1
                        ship_idx = idx
                        break
            else:
                if item_name in items:
                    item_type = cargo_type
                    available = items[item_name]
                    break

        if not item_type:
            yield event.plain_result(f"❌ 货柜和矿舱中没有 {item_name}")
            return

        # 确定卸载数量
        if amount is None or amount > available:
            amount = available

        # 卸载到仓库
        if item_type == '矿石':
            if item_name not in assets['ores']:
                assets['ores'][item_name] = 0
            assets['ores'][item_name] += amount
        elif item_type == '矿物':
            if item_name not in assets['minerals']:
                assets['minerals'][item_name] = 0
            assets['minerals'][item_name] += amount
        elif item_type == '舰船':
            ship_data = cargo['舰船'][ship_idx]
            assets['ships'].append(ship_data)

        # 从货柜扣除
        if item_type == '舰船':
            cargo['舰船'].pop(ship_idx)
            if not cargo['舰船']:
                del cargo['舰船']
        else:
            cargo[item_type][item_name] -= amount
            if cargo[item_type][item_name] <= 0:
                del cargo[item_type][item_name]
            if not cargo[item_type]:
                del cargo[item_type]

        self.save_players()

        text = f"✅ 卸载完成\n\n🚀 舰船：{ship_name}\n📍 地点：{system}空间站\n\n"
        if item_type == '舰船':
            text += f"🚀 {item_name}"
        else:
            text += f"⛏️ {item_name} × {amount}"
        yield event.plain_result(text)

    @filter.command("游戏货柜")
    async def show_cargo(self, event: AstrMessageEvent):
        """查看当前舰船货柜和矿舱"""
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)

        ship = self.get_player_ship(player)
        if not ship:
            yield event.plain_result("❌ 没有驾驶舰船")
            return

        ship_name = ship['name']
        ship_data = self.SHIPS_DATA.get(ship_name, {})
        cargo_capacity = ship_data.get('cargo', 0)
        ore_hold_capacity = ship_data.get('ore_hold', 0)
        cargo = ship.get('cargo', {})
        ore_hold = ship.get('ore_hold', {})

        text = f"📦 舰船货柜\n\n🚀 {ship_name}\n"

        # 显示矿舱信息（如果有）
        if ore_hold_capacity > 0:
            ore_hold_volume = 0
            for ore_name, amount in ore_hold.items():
                ore_data = self.ORES_DATA.get(ore_name, {})
                volume = ore_data.get('volume', 0.1)
                ore_hold_volume += amount * volume
            text += f"⛏️ 矿舱容量：{ore_hold_volume:.2f}/{ore_hold_capacity}m³\n"

        # 显示货柜信息
        if cargo_capacity > 0:
            # 计算当前使用
            cargo_volume = 0
            for item_type, items in cargo.items():
                if item_type == '舰船':
                    for ship_data in items:
                        loaded_ship_name = ship_data['name']
                        ship_volume = self.SHIPS_DATA.get(loaded_ship_name, {}).get('volume', 1000)
                        cargo_volume += ship_volume
                else:
                    for item_name, amount in items.items():
                        if item_type == '矿石':
                            ore_data = self.ORES_DATA.get(item_name, {})
                            volume = ore_data.get('volume', 0.1)
                        else:
                            volume = 0.01
                        cargo_volume += amount * volume

            text += f"📦 货柜容量：{cargo_volume:.2f}/{cargo_capacity}m³\n\n"
        else:
            text += "无货柜\n\n"

        # 显示矿舱内容
        if ore_hold:
            text += "【矿舱】\n"
            for ore_name, amount in ore_hold.items():
                text += f"  ⛏️ {ore_name}：{amount}\n"
            text += "\n"

        # 显示货柜内容
        if cargo:
            for item_type, items in cargo.items():
                text += f"【{item_type}】\n"
                if item_type == '舰船':
                    for ship_data in items:
                        text += f"  🚀 {ship_data['name']} (ID:{ship_data['id']})\n"
                else:
                    for item_name, amount in items.items():
                        text += f"  ⛏️ {item_name}：{amount}\n"

        if not ore_hold and not cargo:
            text += "货柜和矿舱都为空"

        yield event.plain_result(text)

    # ========== 辅助方法 ==========
    def get_player_ship(self, player: Dict) -> Optional[Dict]:
        ship_id = player.get('ship_id')
        if ship_id is None:
            return None
        location = player['location'].replace('小行星带', '')
        for ship in player['assets'].get(location, {}).get('ships', []):
            if ship['id'] == ship_id:
                return ship
        return None
    
    def get_system_security(self, system: str) -> str:
        sec = self.SYSTEM_SECURITY.get(system)
        if sec is None:
            return "未知"
        # 截取两位小数，不四舍五入
        sec_truncated = int(sec * 100) / 100
        if sec >= 0.5:
            return f"{sec_truncated:.2f} 高安"
        elif sec >= 0.1:
            return f"{sec_truncated:.2f} 低安"
        else:
            return f"{sec_truncated:.2f} 00区"
    
    def get_system_security_type(self, system: str) -> str:
        sec = self.SYSTEM_SECURITY.get(system, 1.0)
        if sec >= 0.5:
            return "high"
        elif sec >= 0.1:
            return "low"
        else:
            return "null"
    
    def find_path(self, start: str, target: str) -> Optional[List[str]]:
        if start == target:
            return [start]
        if start not in self.GATE_CONNECTIONS or target not in self.GATE_CONNECTIONS:
            return None
        queue = deque([(start, [start])])
        visited = {start}
        while queue:
            current, path = queue.popleft()
            for neighbor in self.GATE_CONNECTIONS.get(current, []):
                if neighbor == target:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        return None
    
    def calculate_jump_time(self, ship_name: str) -> float:
        ship_data = self.SHIPS_DATA.get(ship_name, {})
        align_time = ship_data.get('align', 10)
        warp_speed = ship_data.get('warp', 3.0)
        warp_time = 30 / warp_speed
        gate_time = 10
        return align_time + warp_time + gate_time

    # ========== 星系导航 ==========
    @filter.command("游戏星系")
    async def show_system_info(self, event: AstrMessageEvent):
        """查看当前星系信息"""
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        system = player['location'].replace('小行星带', '')
        security = self.get_system_security(system)
        sec_type = self.get_system_security_type(system)
        
        text = f"""🌌 星系信息

📍 当前位置：{system}
🔒 安全等级：{security}
"""
        
        # 小行星带信息
        if sec_type == "high":
            text += "\n⛏️ 小行星带：\n  凡晶石、灼烧岩、干焦岩、斜长岩"
        elif sec_type == "low":
            text += "\n⛏️ 小行星带：\n  奥贝尔石、水硼砂、杰斯贝矿、同位原矿、希莫非特、片麻岩"
        else:
            text += "\n⛏️ 小行星带：\n  黑赭石、灰岩、艾克诺岩、双多特石、克洛基石、基腹断岩"
        
        # 刷怪点信息
        available_levels = self.get_rat_level_by_security(security_value)
        text += "\n\n👾 刷怪点：\n"
        for level in available_levels:
            rat_data = self.RAT_DATA[level]
            text += f"  {level}级 - {rat_data['name']} (推荐:{rat_data['ship']})\n"
        
        # 空间站
        if system in self.NPC_STATIONS:
            text += f"\n\n🛰️ 空间站：有NPC空间站"
            if system == self.MARKET_SYSTEM:
                text += "（有市场）"
        else:
            text += "\n\n🛰️ 空间站：无"
        
        yield event.plain_result(text)

    @filter.command("游戏星图")
    async def show_starmap(self, event: AstrMessageEvent):
        """查看星图"""
        args = event.message_str.split()[1:]
        
        if len(args) == 0:
            # 显示所有星域
            text = "🌌 星域列表\n\n"
            for region_name, constellations in self.REGIONS.items():
                system_count = sum(len(systems) for systems in constellations.values())
                text += f"📍 {region_name} - {len(constellations)}个星座，{system_count}个星系\n"
            text += "\n使用 /游戏星图 <星域/星座/星系> 查看详情"
            yield event.plain_result(text)
            return
        
        query = args[0]
        
        # 检查是否是星域
        if query in self.REGIONS:
            constellations = self.REGIONS[query]
            text = f"🌌 {query} 星域\n\n"
            for constellation_name, systems in constellations.items():
                # 计算该星座的平均安全等级
                total_sec = 0
                valid_systems = 0
                for system in systems:
                    sec = self.SYSTEM_SECURITY.get(system)
                    if sec is not None:
                        total_sec += sec
                        valid_systems += 1
                if valid_systems > 0:
                    avg_sec = total_sec / valid_systems
                    # 截取两位小数，不四舍五入
                    sec_text = f"{int(avg_sec * 100) / 100:.2f}"
                else:
                    sec_text = "未知"
                text += f"📍 {constellation_name}星座   {sec_text}\n"
            text += f"\n总计：{len(constellations)}个星座"
            yield event.plain_result(text)
            return
        
        # 检查是否是星座
        for region_name, constellations in self.REGIONS.items():
            if query in constellations:
                systems = constellations[query]
                text = f"🌌 {query} 星座（{region_name}星域）\n\n"
                for system in systems:
                    sec = self.get_system_security(system)
                    has_station = "🛰️" if system in self.NPC_STATIONS else ""
                    text += f"📍 {system} [{sec}] {has_station}\n"
                yield event.plain_result(text)
                return
        
        # 检查是否是星系
        if query in self.GATE_CONNECTIONS:
            connections = self.GATE_CONNECTIONS.get(query, [])
            security = self.get_system_security(query)
            text = f"🌌 {query} 星系\n\n"
            text += f"🔒 安全等级：{security}\n\n"
            text += "🔗 星门连接：\n"
            for system in connections:
                sec = self.get_system_security(system)
                has_station = "🛰️" if system in self.NPC_STATIONS else ""
                text += f"  → {system} [{sec}] {has_station}\n"
            yield event.plain_result(text)
            return
        
        yield event.plain_result(f"❌ 未找到：{query}")

    @filter.command("游戏导航")
    async def start_navigation(self, event: AstrMessageEvent):
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        args = event.message_str.split()[1:]
        if len(args) < 1:
            yield event.plain_result("❌ 用法：/游戏导航 <目标星系>")
            return
        
        target_system = args[0]
        if target_system not in self.GATE_CONNECTIONS:
            yield event.plain_result(f"❌ 未知星系：{target_system}")
            return
        
        current_system = player['location'].replace('小行星带', '')
        if current_system == target_system:
            yield event.plain_result(f"❌ 已经在{target_system}了")
            return
        
        if player['status'] != '待机':
            yield event.plain_result(f"❌ 当前状态为{player['status']}，无法导航")
            return
        
        path = self.find_path(current_system, target_system)
        if not path:
            yield event.plain_result(f"❌ 无法到达{target_system}")
            return
        
        ship = self.get_player_ship(player)
        if not ship:
            yield event.plain_result("❌ 没有驾驶舰船")
            return
        
        jump_time = self.calculate_jump_time(ship['name'])
        total_time = jump_time * (len(path) - 1)
        
        player['status'] = '导航中'
        player['navigating'] = {
            "target": target_system,
            "path": path,
            "current_step": 0,
            "total_steps": len(path) - 1,
            "current": current_system,
            "start_time": time.time(),
            "jump_time": jump_time,
        }
        self.save_players()
        
        path_text = " → ".join(path)
        yield event.plain_result(f"🚀 开始导航\n\n📍 路线：{path_text}\n📊 总计：{len(path)-1}跳\n⏱️ 预计：{total_time/60:.1f}分钟")

    @filter.command("游戏停止导航")
    async def stop_navigation(self, event: AstrMessageEvent):
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        if not player.get('navigating'):
            # 检查是否有运输任务
            if player.get('transporting'):
                yield event.plain_result(
                    "❌ 当前正在执行运输任务\n"
                    "运输过程中的导航不能单独停止\n"
                    "输入 /游戏停止运输 停止整个运输任务"
                )
            else:
                yield event.plain_result("❌ 当前没有进行导航")
            return
        
        # 检查是否是运输任务中的导航
        if player.get('transporting'):
            yield event.plain_result(
                "❌ 当前正在执行运输任务\n"
                "运输过程中的导航不能单独停止\n"
                "输入 /游戏停止运输 停止整个运输任务"
            )
            return
        
        # 检查是否是挖矿过程中的导航（00区卸货导航）
        if player.get('mining'):
            mining = player['mining']
            phase = mining.get('phase', 'mining')
            if phase in ['unloading', 'returning']:
                phase_name = '导航去空间站卸货' if phase == 'unloading' else '返回挖矿点'
                yield event.plain_result(
                    "❌ 当前正在挖矿过程中的导航阶段\n"
                    f"阶段：{phase_name}\n"
                    "挖矿过程中的导航不能单独停止\n"
                    "输入 /游戏停止挖矿 停止整个挖矿任务\n"
                    "（矿石将保留在船上矿舱中）"
                )
                return
        
        # 先结算导航进度，获取当前实际位置
        nav_result = self.settle_navigation(player)
        
        # 如果导航已经完成
        if nav_result:
            self.save_players()
            yield event.plain_result(nav_result)
            return
        
        nav = player['navigating']
        current = nav['current']
        
        # 移动当前驾驶的舰船到当前位置
        self._move_player_ship(player, current)
        
        player['status'] = '待机'
        player['location'] = current
        player['navigating'] = None
        self.save_players()
        
        yield event.plain_result(f"⏹️ 导航已停止\n📍 当前位置：{current}")

    @filter.command("游戏导航状态")
    async def navigation_status(self, event: AstrMessageEvent):
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        self.settle_navigation(player)
        
        if not player.get('navigating'):
            # 检查是否有运输任务
            transport = player.get('transporting')
            if transport:
                yield event.plain_result(
                    f"🚛 当前正在执行运输任务\n"
                    f"📍 状态：{transport['status']}\n"
                    f"🔄 往返次数：{transport['trip_count']}\n\n"
                    f"输入 /游戏运输状态 查看详细进度"
                )
            else:
                yield event.plain_result("📍 当前没有进行导航")
            return
        
        nav = player['navigating']
        path = nav['path']
        current_step = nav['current_step']
        total_steps = nav['total_steps']
        
        # 构建带高亮的路线显示
        highlighted_path = []
        for i, system in enumerate(path):
            if i < current_step:
                highlighted_path.append(f"✅{system}")  # 已经过
            elif i == current_step:
                highlighted_path.append(f"📍{system}")  # 当前位置
            else:
                highlighted_path.append(f"⏳{system}")  # 未到达
        
        path_text = " → ".join(highlighted_path)
        progress = current_step / total_steps * 100
        
        # 计算下一跳预计时间
        jump_time = nav['jump_time']
        elapsed = time.time() - nav['start_time']
        time_in_current_jump = elapsed - (current_step * jump_time)
        time_to_next = max(0, jump_time - time_in_current_jump)
        
        # 检查是否是运输任务中的导航
        transport = player.get('transporting')
        if transport:
            text = f"""🚛 运输任务 - 导航中

📍 路线：{path_text}
📊 进度：{current_step}/{total_steps} 跳 ({progress:.0f}%)
🌌 当前位置：{nav['current']}
🎯 目标：{nav['target']}
⏱️ 下一跳：约{time_to_next:.0f}秒

🔄 运输往返：{transport['trip_count']}次
📋 运输状态：{transport['status']}"""
        else:
            text = f"""🚀 导航状态

📍 路线：{path_text}
📊 进度：{current_step}/{total_steps} 跳 ({progress:.0f}%)
🌌 当前位置：{nav['current']}
🎯 目标：{nav['target']}
⏱️ 下一跳：约{time_to_next:.0f}秒"""
        
        if current_step < len(path) - 1:
            text += f"\n➡️ 下一星系：{path[current_step + 1]}"
        
        yield event.plain_result(text)

    @filter.command("游戏运输")
    async def auto_transport(self, event: AstrMessageEvent):
        """自动在两个星系之间运输物品"""
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        args = event.message_str.split()[1:]
        if len(args) < 2:
            yield event.plain_result("❌ 用法：/游戏运输 <起始星系> <目标星系>")
            return
        
        source_system = args[0]
        target_system = args[1]
        
        # 检查星系是否存在
        if source_system not in self.GATE_CONNECTIONS:
            yield event.plain_result(f"❌ 未知星系：{source_system}")
            return
        if target_system not in self.GATE_CONNECTIONS:
            yield event.plain_result(f"❌ 未知星系：{target_system}")
            return
        
        if source_system == target_system:
            yield event.plain_result("❌ 起始星系和目标星系不能相同")
            return
        
        # 检查当前状态
        if player['status'] != '待机':
            yield event.plain_result(f"❌ 当前状态为{player['status']}，无法开始运输")
            return
        
        # 检查是否已有运输任务
        if player.get('transporting'):
            yield event.plain_result("❌ 已有进行中的运输任务，请先停止当前任务")
            return
        
        # 检查起始星系是否有物品
        source_assets = player['assets'].get(source_system, {})
        has_items = (
            source_assets.get('ores') or 
            source_assets.get('minerals') or 
            source_assets.get('ships')
        )
        
        if not has_items:
            yield event.plain_result(f"❌ {source_system}没有可运输的物品")
            return
        
        # 检查舰船
        ship = self.get_player_ship(player)
        if not ship:
            yield event.plain_result("❌ 没有驾驶舰船")
            return
        
        # 检查是否有货柜或矿舱
        ship_data = self.SHIPS_DATA.get(ship['name'], {})
        if ship_data.get('cargo', 0) <= 0 and ship_data.get('ore_hold', 0) <= 0:
            yield event.plain_result("❌ 舰船没有货柜或矿舱，无法运输")
            return
        
        # 启动运输任务
        player['transporting'] = {
            'source': source_system,
            'target': target_system,
            'status': '准备中',
            'trip_count': 0,
            'start_time': time.time()
        }
        self.save_players()
        
        yield event.plain_result(
            f"🚛 自动运输任务开始\n\n"
            f"📍 起始星系：{source_system}\n"
            f"🎯 目标星系：{target_system}\n"
            f"🚀 运输舰船：{ship['name']}\n\n"
            f"运输流程：\n"
            f"1. 在{source_system}装载物品\n"
            f"2. 导航到{target_system}\n"
            f"3. 卸载物品\n"
            f"4. 返回{source_system}继续装载\n"
            f"5. 重复直到物品全部转移\n\n"
            f"输入 /游戏运输状态 查看进度\n"
            f"输入 /游戏停止运输 停止任务"
        )
        
        # 启动运输循环
        asyncio.create_task(self._transport_loop(user_id))

    @filter.command("游戏运输状态")
    async def transport_status(self, event: AstrMessageEvent):
        """查看运输任务状态"""
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        transport = player.get('transporting')
        if not transport:
            yield event.plain_result("📍 当前没有进行运输任务")
            return
        
        elapsed = time.time() - transport['start_time']
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        
        text = f"""🚛 运输任务状态

📍 起始星系：{transport['source']}
🎯 目标星系：{transport['target']}
📊 状态：{transport['status']}
🔄 往返次数：{transport['trip_count']}
⏱️ 运行时间：{hours}小时{minutes}分钟"""
        
        yield event.plain_result(text)

    @filter.command("游戏停止运输")
    async def stop_transport(self, event: AstrMessageEvent):
        """停止运输任务"""
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        if not player.get('transporting'):
            yield event.plain_result("❌ 当前没有进行运输任务")
            return
        
        transport = player['transporting']
        trip_count = transport['trip_count']
        
        # 清除运输状态
        player['transporting'] = None
        
        # 如果正在导航，先结算导航
        if player['status'] == '导航中':
            self.settle_navigation(player)
        
        # 如果不在待机状态，设置为待机
        if player['status'] != '待机':
            player['status'] = '待机'
        
        self.save_players()
        
        yield event.plain_result(
            f"⏹️ 运输任务已停止\n\n"
            f"🔄 已完成往返：{trip_count}次\n"
            f"📍 当前位置：{player['location']}"
        )

    async def _transport_loop(self, user_id: str):
        """运输循环任务"""
        while True:
            try:
                # 重新加载最新玩家数据（避免覆盖其他修改）
                latest_players = self.load_players()
                if user_id not in latest_players:
                    logger.info(f"运输任务：玩家 {user_id} 不存在，停止运输")
                    break
                
                # 更新内存中的玩家数据
                self.players[user_id] = latest_players[user_id]
                player = self.players[user_id]
                
                transport = player.get('transporting')
                if not transport:
                    logger.info(f"运输任务：玩家 {user_id} 没有运输任务，停止")
                    break
                
                source_system = transport['source']
                target_system = transport['target']
                current_location = player['location'].replace('小行星带', '')
                
                # 检查是否需要装载（在起始星系）
                if current_location == source_system:
                    # 检查起始星系是否还有物品
                    source_assets = player['assets'].get(source_system, {})
                    has_items = (
                        source_assets.get('ores') or 
                        source_assets.get('minerals') or 
                        source_assets.get('ships')
                    )
                    
                    if not has_items:
                        # 运输完成
                        transport['status'] = '已完成'
                        self.save_players()
                        logger.info(f"运输任务完成：{source_system} -> {target_system}")
                        break
                    
                    # 装载物品
                    transport['status'] = f'在{source_system}装载中'
                    logger.info(f"运输任务：在{source_system}装载物品")
                    
                    # 执行装载逻辑（简化版，装载所有物品）
                    ship = self.get_player_ship(player)
                    if ship:
                        # 初始化货柜和矿舱
                        if 'cargo' not in ship:
                            ship['cargo'] = {}
                        if 'ore_hold' not in ship:
                            ship['ore_hold'] = {}
                        
                        ship_data = self.SHIPS_DATA.get(ship['name'], {})
                        cargo_capacity = ship_data.get('cargo', 0)
                        ore_hold_capacity = ship_data.get('ore_hold', 0)
                        
                        current_cargo_volume = self._get_cargo_volume(ship.get('cargo', {}))
                        current_ore_hold_volume = self._get_cargo_volume(ship.get('ore_hold', {}))
                        available_cargo_space = cargo_capacity - current_cargo_volume
                        available_ore_hold_space = ore_hold_capacity - current_ore_hold_volume
                        
                        # 装载矿石（优先矿舱）
                        for ore_name, ore_amount in list(source_assets.get('ores', {}).items()):
                            item_volume = self._get_item_volume('矿石', ore_name)
                            remaining = ore_amount
                            
                            # 先装矿舱
                            if available_ore_hold_space > 0:
                                max_load = int(available_ore_hold_space / item_volume)
                                load_amount = min(remaining, max_load)
                                if load_amount > 0:
                                    source_assets['ores'][ore_name] -= load_amount
                                    if source_assets['ores'][ore_name] <= 0:
                                        del source_assets['ores'][ore_name]
                                    if ore_name not in ship['ore_hold']:
                                        ship['ore_hold'][ore_name] = 0
                                    ship['ore_hold'][ore_name] += load_amount
                                    available_ore_hold_space -= load_amount * item_volume
                                    remaining -= load_amount
                            
                            # 再装货柜
                            if remaining > 0 and available_cargo_space > 0:
                                max_load = int(available_cargo_space / item_volume)
                                load_amount = min(remaining, max_load)
                                if load_amount > 0:
                                    if ore_name in source_assets.get('ores', {}):
                                        source_assets['ores'][ore_name] -= load_amount
                                        if source_assets['ores'][ore_name] <= 0:
                                            del source_assets['ores'][ore_name]
                                    if '矿石' not in ship['cargo']:
                                        ship['cargo']['矿石'] = {}
                                    if ore_name not in ship['cargo']['矿石']:
                                        ship['cargo']['矿石'][ore_name] = 0
                                    ship['cargo']['矿石'][ore_name] += load_amount
                                    available_cargo_space -= load_amount * item_volume
                        
                        # 装载矿物（只能货柜）
                        for mineral_name, mineral_amount in list(source_assets.get('minerals', {}).items()):
                            item_volume = 0.01
                            max_load = int(available_cargo_space / item_volume)
                            load_amount = min(mineral_amount, max_load)
                            if load_amount > 0:
                                source_assets['minerals'][mineral_name] -= load_amount
                                if source_assets['minerals'][mineral_name] <= 0:
                                    del source_assets['minerals'][mineral_name]
                                if '矿物' not in ship['cargo']:
                                    ship['cargo']['矿物'] = {}
                                if mineral_name not in ship['cargo']['矿物']:
                                    ship['cargo']['矿物'][mineral_name] = 0
                                ship['cargo']['矿物'][mineral_name] += load_amount
                                available_cargo_space -= load_amount * item_volume
                        
                        # 装载舰船（只能货柜）
                        for target_ship in list(source_assets.get('ships', [])):
                            if target_ship['id'] == player.get('ship_id'):
                                continue
                            # 检查被装载舰船的货柜是否为空
                            target_cargo = target_ship.get('cargo', {})
                            if target_cargo and self._get_cargo_volume(target_cargo) > 0:
                                continue
                            # 获取舰船实际体积
                            target_ship_name = target_ship['name']
                            item_volume = self.SHIPS_DATA.get(target_ship_name, {}).get('volume', 1000)
                            if available_cargo_space < item_volume:
                                break
                            # 从仓库扣除
                            source_assets['ships'].remove(target_ship)
                            # 装载到货柜
                            if '舰船' not in ship['cargo']:
                                ship['cargo']['舰船'] = []
                            ship['cargo']['舰船'].append(target_ship)
                            available_cargo_space -= item_volume
                    
                    # 保存装载后的数据
                    self.save_players()
                    logger.info(f"运输任务：装载完成，保存数据")
                    await asyncio.sleep(1)  # 短暂延迟
                    
                    # 开始导航到目标星系
                    transport['status'] = f'导航到{target_system}'
                    self.save_players()
                    
                    path = self.find_path(source_system, target_system)
                    if path:
                        player['status'] = '导航中'
                        player['navigating'] = {
                            'target': target_system,
                            'path': path,
                            'current_step': 0,
                            'total_steps': len(path) - 1,
                            'current': source_system,
                            'start_time': time.time(),
                            'jump_time': self.calculate_jump_time(ship['name']) if ship else 20
                        }
                        self.save_players()
                        logger.info(f"运输任务：开始导航到{target_system}")
                
                # 检查是否到达目标星系
                elif current_location == target_system and player.get('navigating') is None:
                    # 卸载物品
                    transport['status'] = f'在{target_system}卸载中'
                    logger.info(f"运输任务：在{target_system}卸载物品")
                    
                    ship = self.get_player_ship(player)
                    if ship:
                        if target_system not in player['assets']:
                            player['assets'][target_system] = {'minerals': {}, 'ores': {}, 'ships': []}
                        target_assets = player['assets'][target_system]
                        
                        # 卸载矿舱中的矿石
                        for ore_name, amount in list(ship.get('ore_hold', {}).items()):
                            if ore_name not in target_assets['ores']:
                                target_assets['ores'][ore_name] = 0
                            target_assets['ores'][ore_name] += amount
                        ship['ore_hold'] = {}
                        
                        # 卸载货柜中的物品
                        cargo = ship.get('cargo', {})
                        for item_type, items in list(cargo.items()):
                            if item_type == '舰船':
                                for ship_data in items:
                                    target_assets['ships'].append(ship_data)
                            else:
                                for item_name, amount in items.items():
                                    if item_type == '矿石':
                                        if item_name not in target_assets['ores']:
                                            target_assets['ores'][item_name] = 0
                                        target_assets['ores'][item_name] += amount
                                    elif item_type == '矿物':
                                        if item_name not in target_assets['minerals']:
                                            target_assets['minerals'][item_name] = 0
                                        target_assets['minerals'][item_name] += amount
                        ship['cargo'] = {}
                    
                    transport['trip_count'] += 1
                    # 保存卸载后的数据
                    self.save_players()
                    logger.info(f"运输任务：卸载完成，已往返{transport['trip_count']}次")
                    await asyncio.sleep(1)  # 短暂延迟
                    
                    # 返回起始星系
                    transport['status'] = f'返回{source_system}'
                    self.save_players()
                    
                    path = self.find_path(target_system, source_system)
                    if path:
                        player['status'] = '导航中'
                        player['navigating'] = {
                            'target': source_system,
                            'path': path,
                            'current_step': 0,
                            'total_steps': len(path) - 1,
                            'current': target_system,
                            'start_time': time.time(),
                            'jump_time': self.calculate_jump_time(ship['name']) if ship else 20
                        }
                        self.save_players()
                        logger.info(f"运输任务：开始返回{source_system}")
                
                # 等待一段时间再检查
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"运输循环出错: {e}")
                import traceback
                logger.error(traceback.format_exc())
                await asyncio.sleep(10)  # 出错后等待更长时间

    def settle_navigation(self, player: Dict) -> str:
        if not player.get('navigating'):
            return ""
        
        nav = player['navigating']
        elapsed = time.time() - nav['start_time']
        jump_time = nav['jump_time']
        
        completed_jumps = int(elapsed / jump_time)
        
        if completed_jumps > nav['current_step']:
            nav['current_step'] = min(completed_jumps, nav['total_steps'])
            nav['current'] = nav['path'][nav['current_step']]
            player['location'] = nav['current']
            
            if nav['current_step'] >= nav['total_steps']:
                target = nav['target']
                # 移动当前驾驶的舰船到目标星系
                self._move_player_ship(player, target)
                player['status'] = '待机'
                player['navigating'] = None
                self.save_players()
                return f"🎉 导航完成！已到达{target}"
            
            # 保存中间进度
            self.save_players()
        
        return ""

    def _move_player_ship(self, player: Dict, target_system: str):
        """将玩家当前驾驶的舰船移动到目标星系"""
        ship_id = player.get('ship_id')
        if not ship_id:
            return
        
        # 找到当前星系
        current_system = None
        current_ship = None
        for system, assets in player['assets'].items():
            for idx, ship in enumerate(assets.get('ships', [])):
                if ship['id'] == ship_id:
                    current_system = system
                    current_ship = ship
                    ship_idx = idx
                    break
            if current_ship:
                break
        
        if not current_ship or current_system == target_system:
            return
        
        # 从当前星系移除舰船
        player['assets'][current_system]['ships'].pop(ship_idx)
        
        # 添加到目标星系
        if target_system not in player['assets']:
            player['assets'][target_system] = {"minerals": {}, "ores": {}, "ships": []}
        if 'ships' not in player['assets'][target_system]:
            player['assets'][target_system]['ships'] = []
        player['assets'][target_system]['ships'].append(current_ship)
        
        # 保存玩家数据（由调用方负责保存，这里不重复保存）

    # ========== 挖矿系统 ==========
    def get_mining_speed(self, ship_name: str) -> float:
        return self.SHIPS_DATA.get(ship_name, {}).get("mining", 0)
    
    def get_ore_distribution(self, security: str) -> Dict[str, float]:
        if security == "high":
            return {"凡晶石": 0.45, "灼烧岩": 0.30, "干焦岩": 0.15, "斜长岩": 0.10}
        elif security == "low":
            return {"奥贝尔石": 0.25, "水硼砂": 0.20, "杰斯贝矿": 0.18, 
                    "同位原矿": 0.15, "希莫非特": 0.12, "片麻岩": 0.10}
        elif security == "null":
            return {"黑赭石": 0.22, "灰岩": 0.18, "艾克诺岩": 0.14, 
                    "双多特石": 0.14, "克洛基石": 0.14, "水硼砂": 0.10, "基腹断岩": 0.08}
        return {}

    @filter.command("游戏挖矿")
    async def start_mining(self, event: AstrMessageEvent):
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        if player['mining']:
            # 如果已经在挖矿，提示用户
            mining = player['mining']
            duration = time.time() - mining['start_time']
            yield event.plain_result(
                f"⛏️ 已在挖矿中\n"
                f"📍 地点：{mining['system']}小行星带\n"
                f"⏱️ 已进行：{duration/60:.1f}分钟\n"
                f"🚀 舰船：{mining['ship_name']}\n\n"
                f"输入 /游戏停止挖矿 停止当前挖矿"
            )
            return
        
        if player['status'] != '待机':
            yield event.plain_result(f"❌ 当前状态为{player['status']}，无法挖矿")
            return
        
        ship = self.get_player_ship(player)
        if not ship:
            yield event.plain_result("❌ 没有驾驶舰船")
            return
        
        mining_ships = ["冲锋者级", "回旋者级"]
        if ship['name'] not in mining_ships:
            yield event.plain_result("❌ 需要驾驶采矿船")
            return
        
        system = player['location'].replace('小行星带', '')
        security_value = self.SYSTEM_SECURITY.get(system, 1.0)  # 数值型安等
        security_type = self.get_system_security_type(system)  # 字符串类型（用于显示）
        
        player['status'] = '挖矿中'
        player['mining'] = {
            "start_time": time.time(),
            "system": system,  # 挖矿地点（固定不变）
            "security": security_value,  # 数值型安等，用于比较
            "security_type": security_type,  # 字符串类型，用于显示
            "ship_name": ship['name'],
            "last_settle_time": time.time(),  # 上次结算时间
            "total_volume": 0,  # 累计已结算矿量
            "phase": "mining",  # 当前阶段: mining(挖矿中), unloading(去卸货), returning(返回挖矿点)
            "ore_in_hold": 0,  # 当前矿舱中的矿石体积(m³)
            "target_station": None,  # 目标NPC空间站(00区需要)
        }
        self.save_players()
        
        sec_name = {"high": "高安", "low": "低安", "null": "00区"}.get(security_type, "未知")
        yield event.plain_result(f"⛏️ 开始挖矿\n📍 地点：{system}小行星带 ({sec_name})\n🚀 舰船：{ship['name']}")

    @filter.command("游戏停止挖矿")
    async def stop_mining(self, event: AstrMessageEvent):
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)

        if not player['mining']:
            yield event.plain_result("❌ 当前没有进行挖矿")
            return

        # 先自动结算满舱的矿物
        self.auto_settle_mining(player)

        # 最终结算
        result = self.final_settle_mining(player)
        self.save_players()
        yield event.plain_result(result)

    # ========== 玩家建筑数据 ==========
    # 格式: {星系名称: {"owner": 拥有者ID, "type": "空间站", "name": "建筑名称"}}
    PLAYER_STRUCTURES = {}
    
    def get_mining_storage_system(self, mining_system: str, security: float, ship_name: str = None, player_id: str = None) -> Tuple[str, float, str]:
        """获取挖矿矿石的存储星系和额外导航时间
        
        Args:
            mining_system: 挖矿所在星系
            security: 星系安等
            ship_name: 舰船名称，用于计算导航时间
            player_id: 玩家ID，用于检查是否有权限使用玩家建筑
            
        Returns:
            (存储星系, 往返导航时间(秒), 存储说明)
        """
        if security >= 0:
            # 高安/低安，直接存本地
            return mining_system, 0, ""
        
        # 00区，先检查是否有玩家建筑
        if mining_system in self.PLAYER_STRUCTURES:
            structure = self.PLAYER_STRUCTURES[mining_system]
            # 如果有玩家建筑，直接存到该星系（暂不需要权限检查，后续可扩展）
            return mining_system, 0, f"\n🏢 使用玩家建筑：{structure.get('name', '未知建筑')}\n"
        
        # 00区没有玩家建筑，需要找到最近的NPC空间站
        nearest_npc = self.find_nearest_npc_station(mining_system)
        if not nearest_npc:
            # 找不到NPC空间站，无法存储（这种情况不应该发生）
            return mining_system, 0, ""
        
        # 使用导航功能计算往返导航时间
        nav_time_one_way = self._estimate_nav_time(mining_system, nearest_npc, ship_name)
        round_trip_time = nav_time_one_way * 2  # 往返
        
        return nearest_npc, round_trip_time, f"\n📦 矿石已转运至最近的NPC空间站：{nearest_npc}\n   （往返导航时间约{round_trip_time/60:.1f}分钟）\n"
    
    def _estimate_nav_time(self, from_system: str, to_system: str, ship_name: str = None) -> float:
        """估算两个星系之间的导航时间（秒）
        
        使用现有的导航功能计算实际导航时间
        """
        if from_system == to_system:
            return 0
        
        # 使用find_path获取路径
        path = self.find_path(from_system, to_system)
        if not path:
            return 300  # 默认5分钟
        
        jumps = len(path) - 1  # 跳数 = 路径长度 - 1
        
        if ship_name:
            # 使用实际舰船计算每跳时间
            jump_time = self.calculate_jump_time(ship_name)
        else:
            # 默认使用冲锋者级作为参考
            jump_time = self.calculate_jump_time("冲锋者级")
        
        return jumps * jump_time

    def auto_settle_mining(self, player: Dict) -> float:
        """自动结算挖矿（矿舱满时），返回结算的矿物体积
        
        完整状态机：
        - mining: 正在挖矿，积累矿石到矿舱
        - unloading: 矿舱满，启动导航去空间站卸货（使用真实导航）
        - returning: 卸货完成，启动导航回挖矿点（使用真实导航）
        """
        if not player.get('mining'):
            return 0

        mining = player['mining']
        current_time = time.time()
        mining_system = mining['system']  # 挖矿地点
        security = mining['security']
        ship_name = mining['ship_name']
        phase = mining.get('phase', 'mining')
        
        # 获取当前实际位置（可能被导航改变）
        current_location = player.get('location', mining_system)

        ship_data = self.SHIPS_DATA[ship_name]
        mining_speed = self.get_mining_speed(ship_name)
        ore_hold_capacity = ship_data['ore_hold']

        # 获取存储星系信息（00区需要）
        user_id = str(player.get('user_id', ''))
        storage_system, _, _ = self.get_mining_storage_system(mining_system, security, ship_name, user_id)
        
        # 处理不同阶段的逻辑
        if phase == 'mining':
            # 挖矿阶段：积累矿石到矿舱
            time_since_last = current_time - mining['last_settle_time']
            mined_volume = time_since_last * mining_speed
            
            # 累加到矿舱
            mining['ore_in_hold'] = mining.get('ore_in_hold', 0) + mined_volume
            
            # 检查矿舱是否满了
            if mining['ore_in_hold'] >= ore_hold_capacity:
                # 矿舱满了
                if security >= 0 or mining_system in self.PLAYER_STRUCTURES:
                    # 高安/低安/有玩家建筑：立即卸货（无导航）
                    self._unload_mining_ore(player, storage_system)
                    mining['last_settle_time'] = current_time
                    mining['ore_in_hold'] = 0
                else:
                    # 00区无玩家建筑：启动真实导航去NPC空间站
                    path = self.find_path(current_location, storage_system)
                    if path:
                        mining['phase'] = 'unloading'
                        mining['target_station'] = storage_system
                        player['status'] = '导航中'
                        player['navigating'] = {
                            'target': storage_system,
                            'path': path,
                            'current_step': 0,
                            'total_steps': len(path) - 1,
                            'start_time': current_time,
                            'jump_time': self.calculate_jump_time(ship_name),
                            'current': current_location,
                            'mining_unload': True  # 标记这是挖矿卸货导航
                        }
            
            mining['last_settle_time'] = current_time
                
        elif phase == 'unloading':
            # 正在导航去空间站卸货
            if not player.get('navigating'):
                # 导航已完成，到达空间站
                target_station = mining.get('target_station')
                if target_station:
                    self._unload_mining_ore(player, target_station)
                    mining['ore_in_hold'] = 0
                    
                    # 启动返回导航
                    path = self.find_path(player['location'], mining_system)
                    if path:
                        mining['phase'] = 'returning'
                        player['status'] = '导航中'
                        player['navigating'] = {
                            'target': mining_system,
                            'path': path,
                            'current_step': 0,
                            'total_steps': len(path) - 1,
                            'start_time': current_time,
                            'jump_time': self.calculate_jump_time(ship_name),
                            'current': player['location'],
                            'mining_return': True  # 标记这是挖矿返回导航
                        }
                    else:
                        # 找不到返回路径，停留在空间站
                        logger.warning(f"玩家 {player.get('name', '未知')} 挖矿后找不到返回{mining_system}的路径")
                        mining['phase'] = 'mining'  # 强制回到mining阶段，但位置在空间站
                        player['status'] = '待机'
                else:
                    # target_station为None，异常情况
                    logger.error(f"玩家 {player.get('name', '未知')} 挖矿unloading阶段target_station为None")
                    mining['phase'] = 'mining'
                    player['status'] = '挖矿中'
            # 否则继续导航中，由导航系统自动处理
            
        elif phase == 'returning':
            # 正在导航回挖矿点
            if not player.get('navigating'):
                # 导航已完成，回到挖矿点
                mining['phase'] = 'mining'
                mining['target_station'] = None
                player['status'] = '挖矿中'
                mining['last_settle_time'] = current_time
            # 否则继续导航中，由导航系统自动处理
        
        self.save_players()
        return 0
    
    def _transfer_ore_to_ship_hold(self, player: Dict, mining: Dict) -> float:
        """将挖矿获得的矿石转移到舰船矿舱中
        
        当在00区导航途中停止时，矿石保留在船上
        
        Returns:
            实际转移的矿石体积(m³)
        """
        ship = self.get_player_ship(player)
        if not ship:
            return 0
        
        ore_volume = mining.get('ore_in_hold', 0)
        if ore_volume <= 0:
            return 0
        
        # 获取舰船矿舱容量
        ship_name = ship.get('name', '冲锋者级')
        ship_data = self.SHIPS_DATA.get(ship_name, {})
        ore_hold_capacity = ship_data.get('ore_hold', 5000)
        
        # 计算当前矿舱已用容量
        current_volume = 0
        if 'ore_hold' in ship:
            for ore_name, ore_units in ship['ore_hold'].items():
                ore_data = self.ORES_DATA.get(ore_name, {'volume': 0.1})
                current_volume += ore_units * ore_data['volume']
        
        # 计算可用容量
        available_volume = ore_hold_capacity - current_volume
        if available_volume <= 0:
            # 矿舱已满，无法转移
            logger.warning(f"玩家 {player.get('name', '未知')} 舰船矿舱已满，无法转移矿石")
            return 0
        
        # 实际能转移的矿石量（受容量限制）
        actual_transfer_volume = min(ore_volume, available_volume)
        
        # 获取该星系的矿石分布
        security = mining['security']
        ore_distribution = self.get_ore_distribution(security)
        
        # 确保舰船矿舱存在
        if 'ore_hold' not in ship:
            ship['ore_hold'] = {}
        
        # 按分布比例将矿石存入舰船矿舱
        for ore_name, ratio in ore_distribution.items():
            ore_amount = actual_transfer_volume * ratio
            ore_data = self.ORES_DATA[ore_name]
            ore_units = ore_amount / ore_data['volume']
            
            if ore_units > 0:
                if ore_name not in ship['ore_hold']:
                    ship['ore_hold'][ore_name] = 0
                ship['ore_hold'][ore_name] += ore_units
        
        # 更新挖矿记录中的矿石（减去已转移的部分）
        mining['ore_in_hold'] = ore_volume - actual_transfer_volume
        
        if actual_transfer_volume < ore_volume:
            logger.warning(f"玩家 {player.get('name', '未知')} 舰船矿舱容量不足，部分矿石丢失")
        
        return actual_transfer_volume
    
    def _unload_mining_ore(self, player: Dict, storage_system: str):
        """卸载挖矿获得的矿石到指定存储星系"""
        mining = player['mining']
        ore_volume = mining.get('ore_in_hold', 0)
        
        if ore_volume <= 0:
            return
        
        system = mining['system']
        security = mining['security']
        
        # 确保存储星系资产存在
        if storage_system not in player['assets']:
            player['assets'][storage_system] = {"minerals": {}, "ores": {}, "ships": []}
        if 'ores' not in player['assets'][storage_system]:
            player['assets'][storage_system]['ores'] = {}
        
        # 根据矿石分布结算
        ore_distribution = self.get_ore_distribution(security)
        
        for ore_name, ratio in ore_distribution.items():
            ore_amount = ore_volume * ratio
            ore_data = self.ORES_DATA[ore_name]
            ore_units = ore_amount / ore_data['volume']
            
            if ore_units > 0:
                if ore_name not in player['assets'][storage_system]['ores']:
                    player['assets'][storage_system]['ores'][ore_name] = 0
                player['assets'][storage_system]['ores'][ore_name] += ore_units
        
        # 更新累计矿量
        mining['total_volume'] = mining.get('total_volume', 0) + ore_volume

    def final_settle_mining(self, player: Dict) -> str:
        """最终结算挖矿收益（停止挖矿时调用）
        
        根据当前阶段处理：
        - mining: 结算矿舱中的矿石（如果在00区且矿舱有矿，需要手动处理）
        - to_station: 导航中停止，矿石在船上，需要决定丢弃或保留
        - back: 导航中停止，矿石已卸货，无损失
        """
        if not player.get('mining'):
            return ""

        mining = player['mining']
        current_time = time.time()
        mining_system = mining['system']  # 挖矿地点
        security = mining['security']
        ship_name = mining['ship_name']
        phase = mining.get('phase', 'mining')

        total_duration = current_time - mining['start_time']
        
        # 获取当前实际位置（导航可能改变了位置）
        current_location = player.get('location', mining_system)
        
        result_text = f"⛏️ 挖矿结算\n📍 挖矿地点：{mining_system}\n📍 当前位置：{current_location}\n⏱️ 总时长：{total_duration/60:.1f}分钟\n🚀 舰船：{ship_name}\n"
        
        # 处理不同阶段的停止
        if phase == 'unloading':
            # 正在导航去空间站卸货途中停止
            if player.get('navigating'):
                # 还在导航中，结算导航获取当前位置
                self.settle_navigation(player)
                current_location = player.get('location', current_location)
                
                # 导航还在进行中（未到达），矿石保留在船上
                ore_in_hold = mining.get('ore_in_hold', 0)
                if ore_in_hold > 0:
                    result_text += f"\n⚠️ 导航去空间站途中停止\n"
                    result_text += f"📍 当前停在：{current_location}\n"
                    # 将矿石存入舰船矿舱（实际存储到ship.ore_hold）
                    transferred = self._transfer_ore_to_ship_hold(player, mining)
                    result_text += f"📦 矿石保留在船上矿舱中：{transferred:.2f}m³\n"
                    remaining = mining.get('ore_in_hold', 0)
                    if remaining > 0:
                        result_text += f"💀 矿舱容量不足，矿石丢失：{remaining:.2f}m³\n"
            else:
                # 导航已完成（已经到达空间站），但阶段还没切换到returning
                # 这种情况通常不会发生，但以防万一
                if mining.get('ore_in_hold', 0) > 0:
                    # 矿石还在，说明还没卸货，立即卸货
                    target = mining.get('target_station', current_location)
                    self._unload_mining_ore(player, target)
                    result_text += f"\n✅ 已到达{target}，矿石已卸货\n"
            
        elif phase == 'returning':
            # 正在返回挖矿点途中停止
            if player.get('navigating'):
                # 还在导航中，结算导航获取当前位置
                self.settle_navigation(player)
                current_location = player.get('location', current_location)
                result_text += f"\n✅ 已卸货完成，返回途中停止\n"
                result_text += f"📍 当前停在：{current_location}\n"
            else:
                # 导航已完成，已经回到挖矿点
                result_text += f"\n✅ 已回到挖矿点{mining_system}\n"
        
        # 结算矿舱中剩余的矿石（如果在mining阶段停止）
        if phase == 'mining':
            final_ore = mining.get('ore_in_hold', 0)
            if final_ore > 0:
                if security >= 0 or mining_system in self.PLAYER_STRUCTURES:
                    # 高安/低安/有玩家建筑：可以存到本地
                    self._unload_mining_ore(player, mining_system)
                    result_text += f"\n📦 矿舱矿石已存入{mining_system}：{final_ore:.2f}m³\n"
                else:
                    # 00区无玩家建筑：矿石保留在船上
                    transferred = self._transfer_ore_to_ship_hold(player, mining)
                    result_text += f"\n📦 矿石保留在船上矿舱中：{transferred:.2f}m³\n"
                    remaining = mining.get('ore_in_hold', 0)
                    if remaining > 0:
                        result_text += f"💀 矿舱容量不足，矿石丢失：{remaining:.2f}m³\n"
        
        # 统计总收益
        total_volume = mining.get('total_volume', 0)
        result_text += f"\n📊 总计已存储：{total_volume:.2f}m³ 原矿"

        player['status'] = '待机'
        # 保持当前位置（导航可能已经改变了位置）
        player['mining'] = None
        return result_text

    # ========== 精炼系统 ==========
    @filter.command("游戏矿石")
    async def list_ores(self, event: AstrMessageEvent):
        """查看所有原矿列表"""
        text = """📋 原矿列表

🔷 高安原矿：
  凡晶石、灼烧岩、干焦岩、斜长岩

🔶 低安原矿：
  奥贝尔石、水硼砂、杰斯贝矿、同位原矿、希莫非特、片麻岩

🔴 00区原矿：
  黑赭石、灰岩、艾克诺岩、双多特石、克洛基石、基腹断岩

使用 /游戏提炼表 <原矿名> 查看产出详情"""
        yield event.plain_result(text)

    @filter.command("游戏提炼表")
    async def show_refine_table(self, event: AstrMessageEvent):
        args = event.message_str.split()[1:]
        
        if len(args) == 0:
            # 显示所有原矿提炼表
            text = """📋 原矿提炼产出表（每单位原矿）

🔷 高安原矿：
凡晶石 → 三钛合金×4
灼烧岩 → 三钛合金×1.5 + 类晶体胶矿×1.1
干焦岩 → 类晶体胶矿×0.9 + 类银超金属×0.3
斜长岩 → 三钛合金×1.75 + 类银超金属×0.7

🔶 低安原矿：
奥贝尔石 → 类晶体胶矿×0.9 + 同位聚合体×0.75
水硼砂 → 类银超金属×0.6 + 同位聚合体×1.2
杰斯贝矿 → 类银超金属×1.5 + 超新星诺克石×0.5
同位原矿 → 类晶体胶矿×4.5 + 超新星诺克石×1.2
希莫非特 → 同位聚合体×2.4 + 超新星诺克石×0.9
片麻岩 → 类晶体胶矿×20 + 类银超金属×15 + 同位聚合体×8

🔴 00区原矿：
黑赭石 → 类银超金属×13.6 + 同位聚合体×12 + 超新星诺克石×3.2
灰岩 → 三钛合金×480 + 同位聚合体×10 + 晶状石英核岩×0.8 + 超新星诺克石×1.6 + 超噬矿×0.4
艾克诺岩 → 类晶体胶矿×32 + 类银超金属×12 + 超噬矿×1.2
双多特石 → 类晶体胶矿×32 + 类银超金属×12 + 晶状石英核岩×1.6
克洛基石 → 类晶体胶矿×8 + 类银超金属×20 + 超新星诺克石×8
基腹断岩 → 莫尔石×1.4

使用 /游戏提炼表 <原矿名> 查看单个原矿详情"""
            yield event.plain_result(text)
            return
        
        ore_name = args[0]
        if ore_name not in self.ORES_DATA:
            yield event.plain_result(f"❌ 未知原矿：{ore_name}")
            return
        
        ore_data = self.ORES_DATA[ore_name]
        sec_name = {"high": "高安", "low": "低安", "null": "00区"}.get(ore_data['security'], "未知")
        
        text = f"📋 {ore_name} 提炼信息\n\n"
        text += f"📍 安全区：{sec_name}\n"
        text += f"📦 体积：{ore_data['volume']} m³/单位\n\n"
        text += "🔥 提炼产出（每单位）：\n"
        for mineral, amount in ore_data['yield'].items():
            text += f"  {mineral} ×{amount}\n"
        
        yield event.plain_result(text)

    @filter.command("游戏精炼")
    async def refine_ores(self, event: AstrMessageEvent):
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        args = event.message_str.split()[1:]
        location = player['location'].replace('小行星带', '')
        
        if location not in player['assets']:
            yield event.plain_result(f"❌ 在{location}没有资产")
            return
        
        ores = player['assets'][location].get('ores', {})
        if not ores:
            yield event.plain_result(f"❌ 在{location}没有原矿")
            return
        
        # 解析参数
        if len(args) == 0:
            # 精炼所有
            target_ores = ores.copy()
        elif len(args) == 1:
            # 精炼指定原矿的所有数量
            ore_name = args[0]
            if ore_name not in ores:
                yield event.plain_result(f"❌ 没有 {ore_name}")
                return
            target_ores = {ore_name: ores[ore_name]}
        elif len(args) >= 2:
            # 精炼指定数量
            ore_name = args[0]
            try:
                amount = float(args[1])
            except ValueError:
                yield event.plain_result("❌ 数量必须是数字")
                return
            
            if ore_name not in ores:
                yield event.plain_result(f"❌ 没有 {ore_name}")
                return
            
            if ores[ore_name] < amount:
                yield event.plain_result(f"❌ {ore_name} 只有 {ores[ore_name]:.2f} 单位")
                return
            
            target_ores = {ore_name: amount}
        
        if not target_ores:
            yield event.plain_result("❌ 没有可精炼的原矿")
            return
        
        if 'minerals' not in player['assets'][location]:
            player['assets'][location]['minerals'] = {}
        
        minerals = player['assets'][location]['minerals']
        result_text = f"🔥 精炼完成\n📍 地点：{location}\n\n"
        total_minerals = {}
        
        for ore_name, ore_units in target_ores.items():
            if ore_name not in self.ORES_DATA:
                continue
            
            ore_data = self.ORES_DATA[ore_name]
            yield_per_unit = ore_data['yield']
            
            result_text += f"⛏️ {ore_name}：{ore_units:.2f}单位\n"
            
            for mineral_name, yield_amount in yield_per_unit.items():
                produced = ore_units * yield_amount
                if produced > 0:
                    if mineral_name not in minerals:
                        minerals[mineral_name] = 0
                    minerals[mineral_name] += produced
                    
                    if mineral_name not in total_minerals:
                        total_minerals[mineral_name] = 0
                    total_minerals[mineral_name] += produced
                    
                    result_text += f"   → {mineral_name}：+{produced:.2f}\n"
            
            ores[ore_name] -= ore_units
            if ores[ore_name] <= 0:
                del ores[ore_name]
        
        if total_minerals:
            result_text += "\n📊 精炼总计：\n"
            for mineral_name, amount in sorted(total_minerals.items()):
                result_text += f"  {mineral_name}：{amount:.2f}单位\n"
        
        self.save_players()
        yield event.plain_result(result_text)

    # ========== 制造系统 ==========
    @filter.command("游戏制造")
    async def manufacturing(self, event: AstrMessageEvent):
        args = event.message_str.split()[1:]
        
        if len(args) == 0:
            yield event.plain_result("❌ 用法：/游戏制造 <舰船> [数量]")
            return
        
        ship_name = args[0]
        
        if ship_name not in self.MANUFACTURING_RECIPES:
            available = ", ".join(self.MANUFACTURING_RECIPES.keys())
            yield event.plain_result(f"❌ 无法制造 {ship_name}\n可用舰船：{available}")
            return
        
        # 获取数量
        quantity = 1
        if len(args) >= 2:
            try:
                quantity = int(args[1])
                if quantity < 1:
                    yield event.plain_result("❌ 数量必须大于0")
                    return
            except ValueError:
                yield event.plain_result("❌ 数量必须是整数")
                return
        
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        # 如果只是查看需求（数量为0或不输入数量且不在空间站）
        location = player['location'].replace('小行星带', '')
        
        # 显示制造需求
        recipe = self.MANUFACTURING_RECIPES[ship_name]
        time_seconds = self.MANUFACTURING_TIME[ship_name]
        
        # 计算总需求
        total_recipe = {k: v * quantity for k, v in recipe.items()}
        total_time = time_seconds * quantity
        
        text = f"🔧 {ship_name} 制造信息\n\n"
        text += f"📦 数量：{quantity}艘\n"
        text += f"⏱️ 时间：{self.format_time(total_time)}\n\n"
        text += "📋 所需矿物：\n"
        for mineral, amount in total_recipe.items():
            text += f"  {mineral}：{amount:,.0f}\n"
        
        # 如果玩家只想查看信息，到这里就结束
        if player['status'] != '待机':
            text += "\n⚠️ 当前状态无法制造"
            yield event.plain_result(text)
            return
        
        if location not in self.NPC_STATIONS:
            text += "\n⚠️ 必须在NPC空间站才能制造"
            yield event.plain_result(text)
            return
        
        # 检查材料
        minerals = player['assets'].get(location, {}).get('minerals', {})
        missing = []
        for mineral, amount in total_recipe.items():
            if minerals.get(mineral, 0) < amount:
                missing.append(f"{mineral} (需要{amount:,.0f}, 有{minerals.get(mineral, 0):.0f})")
        
        if missing:
            text += "\n❌ 材料不足：\n" + "\n".join(missing)
            yield event.plain_result(text)
            return
        
        # 扣除材料
        for mineral, amount in total_recipe.items():
            minerals[mineral] -= amount
            if minerals[mineral] <= 0:
                del minerals[mineral]
        
        # 开始制造
        player['status'] = '制造中'
        player['manufacturing'] = {
            "ship": ship_name,
            "quantity": quantity,
            "start_time": time.time(),
            "duration": total_time,
            "location": location,
        }
        self.save_players()
        
        text += f"\n✅ 开始制造 {quantity}艘 {ship_name}"
        yield event.plain_result(text)

    @filter.command("游戏制造状态")
    async def manufacturing_status(self, event: AstrMessageEvent):
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        result = self.settle_manufacturing(player)
        if result:
            yield event.plain_result(result)
            return
        
        if not player.get('manufacturing'):
            yield event.plain_result("📍 当前没有进行制造")
            return
        
        mfg = player['manufacturing']
        elapsed = time.time() - mfg['start_time']
        remaining = max(0, mfg['duration'] - elapsed)
        progress = min(100, elapsed / mfg['duration'] * 100)
        
        text = f"""🔧 制造状态

🚀 制造：{mfg['ship']} ×{mfg.get('quantity', 1)}
📍 地点：{mfg['location']}
📊 进度：{progress:.1f}%
⏱️ 剩余：{self.format_time(remaining)}"""
        
        yield event.plain_result(text)

    def settle_manufacturing(self, player: Dict) -> str:
        if not player.get('manufacturing'):
            return ""
        
        mfg = player['manufacturing']
        elapsed = time.time() - mfg['start_time']
        
        if elapsed >= mfg['duration']:
            ship_name = mfg['ship']
            quantity = mfg.get('quantity', 1)
            location = mfg['location']
            
            if location not in player['assets']:
                player['assets'][location] = {"minerals": {}, "ores": {}, "ships": []}
            if 'ships' not in player['assets'][location]:
                player['assets'][location]['ships'] = []
            
            new_ships = []
            for i in range(quantity):
                new_ship = {
                    "id": player['next_ship_id'],
                    "name": ship_name,
                    "hp_percent": 100,
                    "cargo": {}  # 每条舰船独立的货柜
                }
                player['assets'][location]['ships'].append(new_ship)
                new_ships.append(str(player['next_ship_id']))
                player['next_ship_id'] += 1
            
            player['status'] = '待机'
            player['manufacturing'] = None
            self.save_players()
            
            return f"🎉 制造完成！\n🚀 获得 {quantity}艘 {ship_name}\n📍 已存入 {location} 机库\nID：{', '.join(new_ships)}"
        
        return ""

    def format_time(self, seconds: float) -> str:
        """格式化时间显示"""
        if seconds < 60:
            return f"{seconds:.0f}秒"
        elif seconds < 3600:
            return f"{seconds/60:.0f}分钟"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            mins = int((seconds % 3600) / 60)
            return f"{hours}小时{mins}分钟"
        else:
            days = int(seconds / 86400)
            hours = int((seconds % 86400) / 3600)
            return f"{days}天{hours}小时"

    # ========== 舰船系统 ==========
    @filter.command("游戏舰船")
    async def list_ships(self, event: AstrMessageEvent):
        args = event.message_str.split()[1:]
        
        if len(args) == 0:
            # 显示所有舰船
            text = """🚀 全部舰船列表

⚔️ 作战舰船：
  小鹰级 - DPS:305.4 血量:7816 货柜:150m³ 跃迁:5AU/s 起跳:3s
  海燕级 - DPS:507 血量:10618 货柜:425m³ 跃迁:4.5AU/s 起跳:4s
  巨鸟级 - DPS:774.5 血量:49652 货柜:450m³ 跃迁:4AU/s 起跳:5s
  娜迦级 - DPS:1439.4 血量:53984 货柜:575m³ 跃迁:3.5AU/s 起跳:7s
  鹏鲲级 - DPS:1405.7 血量:142671 货柜:820m³ 跃迁:3AU/s 起跳:13s

⛏️ 采矿舰船：
  冲锋者级 - DPS:39.6 血量:5378 矿舱:5000m³ 挖矿:8.51m³/s 跃迁:5AU/s 起跳:4s
  回旋者级 - DPS:99 血量:14091 矿舱:27500m³ 挖矿:20.96m³/s 跃迁:3AU/s 起跳:12s

🚛 运输舰船：
  狐鼬级 - DPS:49.3 血量:14364 货柜:24114m³ 跃迁:4.7AU/s 起跳:11s
  渡神级 - DPS:0 血量:215993 货柜:1204740m³ 跃迁:1.4AU/s 起跳:42s

使用 /游戏舰船 <舰船名称> 查看详细属性"""
            yield event.plain_result(text)
            return
        
        ship_name = args[0]
        if ship_name not in self.SHIPS_DATA:
            yield event.plain_result(f"❌ 未知舰船：{ship_name}")
            return
        
        ship = self.SHIPS_DATA[ship_name]
        text = f"🚀 {ship_name} 属性\n\n"
        text += f"📋 类型：{ship['type']}\n"
        text += f"⚔️ DPS：{ship['dps']}\n"
        text += f"❤️ 血量：{ship['hp']}\n"
        text += f"📦 货柜：{ship['cargo']}m³\n"
        text += f"🚀 跃迁速度：{ship['warp']}AU/s\n"
        text += f"⏱️ 起跳时间：{ship['align']}秒\n"
        
        if 'mining' in ship:
            text += f"⛏️ 挖矿速度：{ship['mining']}m³/s\n"
            text += f"📦 矿舱：{ship['ore_hold']}m³\n"
        
        # 制造信息
        if ship_name in self.MANUFACTURING_RECIPES:
            recipe = self.MANUFACTURING_RECIPES[ship_name]
            time_seconds = self.MANUFACTURING_TIME[ship_name]
            text += f"\n🔧 制造时间：{self.format_time(time_seconds)}\n"
            text += "📋 制造材料：\n"
            for mineral, amount in recipe.items():
                text += f"  {mineral}：{amount:,.0f}\n"
        
        yield event.plain_result(text)

    @filter.command("游戏机库")
    async def list_hangar(self, event: AstrMessageEvent):
        args = event.message_str.split()[1:]
        
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        # 确定星系
        if len(args) >= 1:
            system = args[0]
            if system not in player['assets']:
                yield event.plain_result(f"📦 {system} 机库\n\n暂无舰船")
                return
        else:
            system = player['location'].replace('小行星带', '')
        
        ships = player['assets'].get(system, {}).get('ships', [])
        
        if not ships:
            yield event.plain_result(f"📦 {system} 机库\n\n暂无舰船")
            return
        
        text = f"📦 {system} 机库\n\n"
        for ship in ships:
            status = "🚀 已装备" if ship['id'] == player.get('ship_id') else "⚓ 待命"
            text += f"ID:{ship['id']} {ship['name']} (血量:{ship.get('hp_percent', 100)}%) {status}\n"
        
        text += "\n使用 /游戏换船 <舰船名称> 更换舰船"
        yield event.plain_result(text)

    @filter.command("游戏换船")
    async def change_ship(self, event: AstrMessageEvent):
        args = event.message_str.split()[1:]
        
        if len(args) < 1:
            yield event.plain_result("❌ 用法：/游戏换船 <舰船名称>")
            return
        
        ship_name = args[0]
        
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        if player['status'] != '待机':
            yield event.plain_result(f"❌ 当前状态为{player['status']}，无法换船")
            return
        
        location = player['location'].replace('小行星带', '')
        
        # 检查是否在空间站
        if location not in self.NPC_STATIONS:
            yield event.plain_result("❌ 必须在空间站才能换船")
            return
        
        # 查找指定名称的舰船
        ships = player['assets'].get(location, {}).get('ships', [])
        target_ship = None
        for ship in ships:
            if ship['name'] == ship_name:
                target_ship = ship
                break
        
        if not target_ship:
            yield event.plain_result(f"❌ 在{location}机库中没有{ship_name}")
            return
        
        player['ship_id'] = target_ship['id']
        self.save_players()

        yield event.plain_result(f"✅ 已驾驶 {ship_name} (ID:{target_ship['id']})")

    # ========== 刷怪系统 ==========
    @filter.command("游戏刷怪")
    async def start_ratting(self, event: AstrMessageEvent):
        """开始刷怪"""
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)

        # 结算之前的刷怪
        if player.get('ratting'):
            self.final_settle_ratting(player)
            self.save_players()

        # 获取当前星系安全等级
        system = player['location'].replace('小行星带', '')
        security = self.SYSTEM_SECURITY.get(system, 1.0)
        available_levels = self.get_rat_level_by_security(security)

        # 每个星系只有一种刷怪等级（取该安全等级范围的第一个）
        level = available_levels[0]
        rat_data = self.RAT_DATA[level]

        # 检查当前舰船
        ship = self.get_player_ship(player)
        if not ship:
            yield event.plain_result("❌ 没有驾驶舰船")
            return

        ship_name = ship['name']
        combat_ships = ["小鹰级", "海燕级", "巨鸟级", "娜迦级", "鹏鲲级"]
        if ship_name not in combat_ships:
            yield event.plain_result("❌ 需要驾驶作战舰船才能刷怪")
            return

        # 检查舰船血量
        if ship.get('hp_percent', 100) <= 0:
            yield event.plain_result("❌ 舰船已损毁，需要维修")
            return

        # 检查状态
        if player['status'] != '待机':
            yield event.plain_result(f"❌ 当前状态为{player['status']}，无法刷怪")
            return

        # 检查舰船是否适合当前星系的刷怪等级
        recommended_ship = rat_data['ship']
        if ship_name != recommended_ship:
            # 截取两位小数，不四舍五入
            security_truncated = int(security * 100) / 100
            text = f"👾 {system} 刷怪点\n\n"
            text += f"🔒 安全等级：{security_truncated:.2f}\n"
            text += f"👾 刷怪等级：{level}级 - {rat_data['name']}\n"
            text += f"🚀 当前舰船：{ship_name}\n"
            text += f"✅ 推荐舰船：{recommended_ship}\n\n"
            text += f"⚠️ 当前舰船不适合刷此等级怪物\n"
            text += f"请更换为{recommended_ship}后重试"
            yield event.plain_result(text)
            return

        # 开始刷怪
        current_time = time.time()
        player['status'] = '刷怪中'
        player['ratting'] = {
            "start_time": current_time,
            "level": level,
            "system": system,
            "ship_name": ship_name,
            "last_settle_time": current_time,  # 上次结算时间
            "total_bounty": 0,  # 累计赏金（已结算）
        }
        self.save_players()

        text = f"👾 开始刷怪\n\n"
        text += f"📍 地点：{system} {rat_data['name']}\n"
        text += f"🚀 舰船：{ship_name}\n"
        text += f"👾 怪物血量：{rat_data['hp']:,}\n"
        text += f"💰 单只赏金：¥{rat_data['bounty']:,}\n"
        if ship_name != recommended_ship:
            text += f"⚠️ 警告：当前舰船{ship_name}不是推荐舰船{recommended_ship}，效率可能较低\n"
        yield event.plain_result(text)

    @filter.command("游戏停止刷怪")
    async def stop_ratting(self, event: AstrMessageEvent):
        """停止刷怪并结算"""
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)

        if not player.get('ratting'):
            yield event.plain_result("❌ 当前没有进行刷怪")
            return

        # 先结算剩余时间的赏金
        self.auto_settle_ratting(player)

        # 最终结算
        result = self.final_settle_ratting(player)
        self.save_players()
        yield event.plain_result(result)

    def auto_settle_ratting(self, player: Dict) -> int:
        """自动结算20分钟内的赏金，返回结算金额"""
        if not player.get('ratting'):
            return 0

        ratting = player['ratting']
        current_time = time.time()
        last_settle_time = ratting['last_settle_time']
        level = ratting['level']
        ship_name = ratting['ship_name']

        # 计算距离上次结算的时间
        duration = current_time - last_settle_time

        # 如果不足20分钟，不结算
        if duration < 1200:  # 20分钟 = 1200秒
            return 0

        rat_data = self.RAT_DATA[level]

        # 获取舰船DPS
        ship_dps = self.SHIPS_DATA.get(ship_name, {}).get('dps', 0)

        # 检查舰船是否有战斗能力
        if ship_dps <= 0:
            return 0

        # 计算击杀时间（含维修延时）
        kill_time = rat_data['hp'] / ship_dps
        repair_delay = self.REPAIR_DELAY.get(ship_name, 45)
        cycle_time = kill_time + repair_delay

        # 计算这20分钟内实际完成的异常数量（考虑完整循环）
        # 20分钟 = 1200秒
        cycles = int(1200 / cycle_time)

        # 计算赏金
        bounty = cycles * rat_data['bounty']

        # 更新玩家数据 - 结算时间点往前推，保留未完成的循环时间
        # 实际经过的完整循环时间
        actual_cycle_time = cycles * cycle_time
        ratting['last_settle_time'] = last_settle_time + actual_cycle_time
        ratting['total_bounty'] += bounty
        player['wallet'] += bounty

        # 保存玩家数据
        self.save_players()

        return bounty

    def final_settle_ratting(self, player: Dict) -> str:
        """最终结算刷怪收益（停止刷怪时调用）"""
        if not player.get('ratting'):
            return ""

        ratting = player['ratting']
        current_time = time.time()
        level = ratting['level']
        system = ratting['system']
        ship_name = ratting['ship_name']

        # 计算距离上次结算的时间（剩余时间）
        duration = current_time - ratting['last_settle_time']
        total_duration = current_time - ratting['start_time']

        rat_data = self.RAT_DATA[level]

        # 获取舰船DPS
        ship_dps = self.SHIPS_DATA.get(ship_name, {}).get('dps', 0)

        # 检查舰船是否有战斗能力
        if ship_dps <= 0:
            player['status'] = '待机'
            player['ratting'] = None
            return "❌ 该舰船无法进行战斗，刷怪已停止"

        # 计算击杀时间
        kill_time = rat_data['hp'] / ship_dps

        # 获取维修延时
        repair_delay = self.REPAIR_DELAY.get(ship_name, 45)

        # 单次循环时间
        cycle_time = kill_time + repair_delay

        # 计算剩余时间内完成的异常数量
        remaining_cycles = int(duration / cycle_time)

        # 计算之前已结算的异常数量
        settled_cycles = int(ratting['total_bounty'] / rat_data['bounty'])

        # 总异常数量 = 已结算 + 剩余
        total_cycles = settled_cycles + remaining_cycles

        # 计算剩余赏金
        remaining_bounty = remaining_cycles * rat_data['bounty']

        # 总赏金 = 已结算 + 剩余
        total_bounty = ratting['total_bounty'] + remaining_bounty

        # 更新玩家数据
        player['wallet'] += remaining_bounty
        player['status'] = '待机'
        player['ratting'] = None

        # 生成结算文本
        result_text = f"👾 刷怪结算\n\n"
        result_text += f"📍 地点：{system} {rat_data['name']}\n"
        result_text += f"⏱️ 总时长：{total_duration/60:.1f}分钟\n"
        result_text += f"🚀 舰船：{ship_name}\n\n"
        result_text += f"👾 完成异常数量：{total_cycles}个\n"
        result_text += f"💰 总赏金：¥{total_bounty:,}\n"

        return result_text

    async def _ratting_auto_settle_loop(self):
        """自动结算循环：每60秒检查一次，为刷怪满20分钟或挖矿满舱的玩家自动结算"""
        logger.info("自动结算循环已启动")
        while True:
            try:
                await asyncio.sleep(60)  # 每60秒检查一次
                # 重新加载最新数据，避免覆盖其他修改
                latest_players = self.load_players()
                has_changes = False

                for user_id, player in latest_players.items():
                    try:
                        # 刷怪自动结算（每20分钟）
                        if player.get('ratting'):
                            # 检查ratting数据结构是否完整
                            ratting = player['ratting']
                            required_fields = ['start_time', 'level', 'system', 'ship_name', 'last_settle_time', 'total_bounty']
                            if not all(field in ratting for field in required_fields):
                                logger.warning(f"玩家 {user_id} 的ratting数据不完整，跳过结算")
                                continue
                            bounty = self.auto_settle_ratting(player)
                            if bounty > 0:
                                logger.info(f"玩家 {user_id} 自动结算赏金: ¥{bounty:,}")
                                has_changes = True

                        # 挖矿自动结算（矿舱满时或导航阶段）
                        if player.get('mining'):
                            # 检查mining数据结构是否完整
                            mining = player['mining']
                            required_fields = ['start_time', 'system', 'security', 'ship_name', 'last_settle_time', 'total_volume']
                            if not all(field in mining for field in required_fields):
                                logger.warning(f"玩家 {user_id} 的mining数据不完整，跳过结算")
                                continue
                            
                            # 如果在导航阶段，先结算导航进度
                            phase = mining.get('phase', 'mining')
                            if phase in ['unloading', 'returning'] and player.get('navigating'):
                                self.settle_navigation(player)
                            
                            volume = self.auto_settle_mining(player)
                            if volume > 0:
                                logger.info(f"玩家 {user_id} 自动结算挖矿: {volume:.2f}m³")
                                has_changes = True
                    except Exception as player_e:
                        logger.error(f"处理玩家 {user_id} 时出错: {player_e}")
                        continue

                if has_changes:
                    # 保存前先重新加载，合并可能的并发修改
                    current_data = self.load_players()
                    for user_id, player in latest_players.items():
                        if user_id in current_data:
                            # 更新所有可能有变化的字段
                            current_data[user_id]['wallet'] = player['wallet']
                            current_data[user_id]['assets'] = player['assets']
                            # 更新所有状态字段（包括可能为None的状态）
                            for field in ['ratting', 'mining', 'manufacturing', 'navigating',
                                          'status', 'location', 'ship_id', 'next_ship_id']:
                                if field in player:
                                    current_data[user_id][field] = player[field]
                    # 更新内存并保存
                    self.players = current_data
                    self.save_players()
                    logger.info("自动结算完成，数据已保存")
            except Exception as e:
                # 出错后继续循环
                logger.error(f"自动结算循环出错: {e}")
                import traceback
                logger.error(traceback.format_exc())
                await asyncio.sleep(60)

    # ========== 市场系统（仅吉他） ==========
    def create_escrow(self, escrow_type: str, item_name: str, quantity: float,
                      owner_id: str, target_id: str = None, related_order: str = None) -> str:
        """创建中介冻结记录"""
        escrow_id = self._generate_escrow_id()
        self.escrow_data[escrow_id] = {
            "escrow_id": escrow_id,
            "type": escrow_type,  # item/currency
            "item_name": item_name,
            "quantity": quantity,
            "owner_id": owner_id,
            "target_id": target_id,
            "related_order": related_order,
            "created_at": time.time(),
            "status": "frozen"
        }
        self.save_escrow()
        return escrow_id

    def release_escrow(self, escrow_id: str, release_to: str, system: str = "吉他", quantity: float = None):
        """解冻中介记录，转移物品/货币
        
        Args:
            escrow_id: 中介ID
            release_to: 接收者用户ID
            system: 星系
            quantity: 释放数量，None表示全部释放
        """
        if escrow_id not in self.escrow_data:
            return False
        
        escrow = self.escrow_data[escrow_id]
        if escrow["status"] != "frozen":
            return False
        
        # 获取目标玩家
        target_player = self.get_player(release_to)
        
        # 确定释放数量
        release_quantity = quantity if quantity is not None else escrow["quantity"]
        
        if escrow["type"] == "item":
            # 物品转移到目标玩家机库
            if system not in target_player['assets']:
                target_player['assets'][system] = {"minerals": {}, "ores": {}, "ships": []}
            
            item_name = escrow["item_name"]
            
            # 根据物品类型存入对应仓库
            if item_name in self.ORES_DATA:
                if 'ores' not in target_player['assets'][system]:
                    target_player['assets'][system]['ores'] = {}
                if item_name not in target_player['assets'][system]['ores']:
                    target_player['assets'][system]['ores'][item_name] = 0
                target_player['assets'][system]['ores'][item_name] += release_quantity
            else:
                if 'minerals' not in target_player['assets'][system]:
                    target_player['assets'][system]['minerals'] = {}
                if item_name not in target_player['assets'][system]['minerals']:
                    target_player['assets'][system]['minerals'][item_name] = 0
                target_player['assets'][system]['minerals'][item_name] += release_quantity
            
            # 更新中介剩余数量
            escrow["quantity"] -= release_quantity
            
        elif escrow["type"] == "currency":
            # 货币转移到目标玩家钱包
            target_player['wallet'] += release_quantity
            # 更新中介剩余数量
            escrow["quantity"] -= release_quantity
        
        # 如果全部释放完毕，标记为已释放
        if escrow["quantity"] <= 0:
            escrow["status"] = "released"
        
        self.save_escrow()
        self.save_players()
        return True

    @filter.command("游戏市场")
    async def show_market(self, event: AstrMessageEvent):
        """查看吉他市场指定物品的订单"""
        args = event.message_str.split()[1:]
        
        if len(args) < 1:
            yield event.plain_result("❌ 用法：/游戏市场 <物品名>")
            return
        
        item_name = args[0]
        system = "吉他"
        
        # 获取该星系的市场订单
        orders = self.market_data.get(system, [])
        
        # 筛选指定物品的订单
        sell_orders = [o for o in orders if o['type'] == 'sell' and o['item_name'] == item_name]
        buy_orders = [o for o in orders if o['type'] == 'buy' and o['item_name'] == item_name]
        
        if not sell_orders and not buy_orders:
            yield event.plain_result(f"📊 {system} 市场 - {item_name}\n\n暂无该物品的订单")
            return
        
        text = f"📊 {system} 市场 - {item_name}\n\n"
        
        # 处理卖单：按价格升序排列，合并同价格订单
        if sell_orders:
            # 按价格升序排序
            sell_orders.sort(key=lambda x: x['price'])
            
            # 合并同价格订单
            price_groups = {}
            for order in sell_orders:
                price = order['price']
                if price not in price_groups:
                    price_groups[price] = 0
                price_groups[price] += order['quantity']
            
            # 取前5个最低价
            sorted_prices = sorted(price_groups.items())[:5]
            
            text += "🔴 卖单（最低价前5）：\n"
            for price, quantity in sorted_prices:
                text += f"  ¥{price:,}/单位 ×{quantity}\n"
        
        # 处理买单：按价格降序排列，合并同价格订单
        if buy_orders:
            # 按价格降序排序
            buy_orders.sort(key=lambda x: x['price'], reverse=True)
            
            # 合并同价格订单
            price_groups = {}
            for order in buy_orders:
                price = order['price']
                if price not in price_groups:
                    price_groups[price] = 0
                price_groups[price] += order['quantity']
            
            # 取前5个最高价
            sorted_prices = sorted(price_groups.items(), key=lambda x: x[0], reverse=True)[:5]
            
            text += "\n🟢 买单（最高价前5）：\n"
            for price, quantity in sorted_prices:
                text += f"  ¥{price:,}/单位 ×{quantity}\n"
        
        text += f"\n使用 /游戏购买 {item_name} [数量] 购买最低价卖单"
        yield event.plain_result(text)

    @filter.command("游戏卖单")
    async def create_sell_order(self, event: AstrMessageEvent):
        """上架卖单"""
        args = event.message_str.split()[1:]
        
        if len(args) < 3:
            yield event.plain_result("❌ 用法：/游戏卖单 <物品名> <数量> <单价>")
            return
        
        item_name = args[0]
        try:
            quantity = float(args[1])
            price = int(args[2])
        except ValueError:
            yield event.plain_result("❌ 数量和单价必须是数字")
            return
        
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        # 检查是否在吉他空间站
        system = "吉他"
        current_system = player['location'].replace('小行星带', '')
        if current_system != system:
            yield event.plain_result(f"❌ 必须在{system}空间站才能上架订单")
            return
        
        # 检查物品是否存在
        assets = player['assets'].get(system, {})
        available = 0
        item_type = None
        
        if item_name in assets.get('ores', {}):
            available = assets['ores'][item_name]
            item_type = 'ore'
        elif item_name in assets.get('minerals', {}):
            available = assets['minerals'][item_name]
            item_type = 'mineral'
        
        if available < quantity:
            yield event.plain_result(f"❌ {item_name} 不足（需要{quantity}，有{available}）")
            return
        
        # 扣除物品，创建中介冻结
        if item_type == 'ore':
            assets['ores'][item_name] -= quantity
            if assets['ores'][item_name] <= 0:
                del assets['ores'][item_name]
        else:
            assets['minerals'][item_name] -= quantity
            if assets['minerals'][item_name] <= 0:
                del assets['minerals'][item_name]
        
        escrow_id = self.create_escrow("item", item_name, quantity, user_id)
        
        # 创建市场订单
        order_id = self._generate_order_id()
        order = {
            "order_id": order_id,
            "system": system,
            "type": "sell",
            "item_type": item_type,
            "item_name": item_name,
            "quantity": quantity,
            "price": price,
            "seller_id": user_id,
            "created_at": time.time(),
            "escrow_id": escrow_id
        }
        
        if system not in self.market_data:
            self.market_data[system] = []
        self.market_data[system].append(order)
        
        self.save_market()
        self.save_players()
        
        yield event.plain_result(f"✅ 卖单上架成功\n📦 {item_name} ×{quantity}\n💰 ¥{price:,}/单位\n📍 {system}\nID: {order_id}")

    @filter.command("游戏买单")
    async def create_buy_order(self, event: AstrMessageEvent):
        """上架买单，如果价格 >= 最低卖单价格则自动成交"""
        args = event.message_str.split()[1:]
        
        if len(args) < 3:
            yield event.plain_result("❌ 用法：/游戏买单 <物品名> <数量> <单价>")
            return
        
        item_name = args[0]
        try:
            quantity = float(args[1])
            price = int(args[2])
        except ValueError:
            yield event.plain_result("❌ 数量和单价必须是数字")
            return
        
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        # 检查是否在吉他空间站
        system = "吉他"
        current_system = player['location'].replace('小行星带', '')
        if current_system != system:
            yield event.plain_result(f"❌ 必须在{system}空间站才能上架订单")
            return
        
        # 检查是否有可匹配的卖单（买单价格 >= 卖单价格）
        sell_orders = [o for o in self.market_data.get(system, [])
                       if o['type'] == 'sell' and o['item_name'] == item_name and o['price'] <= price]
        
        if sell_orders:
            # 有匹配的卖单，自动成交
            # 按价格升序排序（优先成交低价卖单）
            sell_orders.sort(key=lambda x: x['price'])
            
            # 计算需要购买的数量
            remaining_to_buy = quantity
            orders_to_buy = []  # [(order, quantity, actual_price), ...]
            total_cost = 0
            
            for order in sell_orders:
                if remaining_to_buy <= 0:
                    break
                
                # 检查是否是自己的订单
                if order.get('seller_id') == user_id:
                    continue
                
                buy_qty = min(remaining_to_buy, order['quantity'])
                actual_price = order['price']  # 按卖单价格成交
                orders_to_buy.append((order, buy_qty, actual_price))
                total_cost += int(buy_qty * actual_price)
                remaining_to_buy -= buy_qty
            
            if not orders_to_buy:
                # 没有可购买的卖单（都是自己的），创建普通买单
                pass
            else:
                # 检查钱包余额
                if player['wallet'] < total_cost:
                    yield event.plain_result(
                        f"❌ 钱包余额不足以自动成交\n"
                        f"需要：¥{total_cost:,}\n"
                        f"拥有：¥{player['wallet']:,}\n"
                        f"建议降低购买数量或单价"
                    )
                    return
                
                # 执行自动成交
                actual_bought = 0
                for order, buy_qty, actual_price in orders_to_buy:
                    order_cost = int(buy_qty * actual_price)
                    
                    # 扣除买方货币
                    player['wallet'] -= order_cost
                    
                    # 释放卖方的物品中介到买方
                    self.release_escrow(order['escrow_id'], user_id, system, buy_qty)
                    
                    # 给卖方钱包加钱
                    seller = self.get_player(order['seller_id'])
                    seller['wallet'] += order_cost
                    
                    # 更新或删除卖单
                    if buy_qty >= order['quantity']:
                        self.market_data[system].remove(order)
                    else:
                        order['quantity'] -= buy_qty
                    
                    actual_bought += buy_qty
                
                self.save_market()
                self.save_players()
                
                # 计算平均成交价格
                avg_price = int(total_cost / actual_bought) if actual_bought > 0 else 0
                
                result_text = (
                    f"✅ 买单自动成交\n"
                    f"📦 {item_name} ×{actual_bought}\n"
                    f"💰 总花费：¥{total_cost:,}\n"
                    f"📊 平均单价：¥{avg_price:,}\n"
                    f"📍 已存入{system}机库"
                )
                
                # 如果还有剩余未成交的数量，创建剩余买单
                remaining_qty = quantity - actual_bought
                if remaining_qty > 0:
                    remaining_cost = int(remaining_qty * price)
                    if player['wallet'] >= remaining_cost:
                        # 扣除剩余货币，创建中介冻结
                        player['wallet'] -= remaining_cost
                        escrow_id = self.create_escrow("currency", item_name, remaining_cost, user_id)
                        
                        # 创建剩余买单
                        order_id = self._generate_order_id()
                        order = {
                            "order_id": order_id,
                            "system": system,
                            "type": "buy",
                            "item_name": item_name,
                            "quantity": remaining_qty,
                            "price": price,
                            "buyer_id": user_id,
                            "created_at": time.time(),
                            "escrow_id": escrow_id
                        }
                        
                        if system not in self.market_data:
                            self.market_data[system] = []
                        self.market_data[system].append(order)
                        
                        self.save_market()
                        self.save_players()
                        
                        result_text += f"\n\n📋 剩余未成交：{remaining_qty}单位\n已创建买单：¥{price:,}/单位\nID: {order_id}"
                    else:
                        result_text += f"\n\n⚠️ 剩余{remaining_qty}单位未成交\n钱包余额不足创建剩余买单"
                
                yield event.plain_result(result_text)
                return
        
        # 没有匹配的卖单，创建普通买单
        # 计算总价
        total_price = int(quantity * price)
        
        # 检查钱包余额
        if player['wallet'] < total_price:
            yield event.plain_result(f"❌ 钱包余额不足（需要¥{total_price:,}，有¥{player['wallet']:,}）")
            return
        
        # 扣除货币，创建中介冻结
        player['wallet'] -= total_price
        escrow_id = self.create_escrow("currency", item_name, total_price, user_id)
        
        # 创建市场订单
        order_id = self._generate_order_id()
        order = {
            "order_id": order_id,
            "system": system,
            "type": "buy",
            "item_name": item_name,
            "quantity": quantity,
            "price": price,
            "buyer_id": user_id,
            "created_at": time.time(),
            "escrow_id": escrow_id
        }
        
        if system not in self.market_data:
            self.market_data[system] = []
        self.market_data[system].append(order)
        
        self.save_market()
        self.save_players()
        
        yield event.plain_result(f"✅ 买单上架成功\n📦 {item_name} ×{quantity}\n💰 ¥{price:,}/单位\n📍 {system}\nID: {order_id}")

    @filter.command("游戏购买")
    async def buy_from_market(self, event: AstrMessageEvent):
        """自动购买市场最低价卖单"""
        args = event.message_str.split()[1:]
        
        if len(args) < 1:
            yield event.plain_result("❌ 用法：/游戏购买 <物品名> [数量]")
            return
        
        item_name = args[0]
        requested_quantity = float(args[1]) if len(args) > 1 else None
        
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        system = "吉他"
        
        # 查找该物品的卖单，按价格升序排列
        sell_orders = [o for o in self.market_data.get(system, []) 
                       if o['type'] == 'sell' and o['item_name'] == item_name]
        
        if not sell_orders:
            yield event.plain_result(f"❌ {item_name} 暂无卖单")
            return
        
        # 按价格升序排序（最低价在前）
        sell_orders.sort(key=lambda x: x['price'])
        
        # 计算总可用数量
        total_available = sum(o['quantity'] for o in sell_orders)
        
        # 确定购买数量
        if requested_quantity is None:
            buy_quantity = total_available
        else:
            buy_quantity = min(requested_quantity, total_available)
        
        # 计算需要购买哪些订单
        remaining_to_buy = buy_quantity
        orders_to_buy = []  # [(order, quantity), ...]
        total_price = 0
        
        for order in sell_orders:
            if remaining_to_buy <= 0:
                break
            
            # 检查是否是自己的订单
            if order.get('seller_id') == user_id:
                continue
            
            order_quantity = min(remaining_to_buy, order['quantity'])
            orders_to_buy.append((order, order_quantity))
            total_price += int(order_quantity * order['price'])
            remaining_to_buy -= order_quantity
        
        if not orders_to_buy:
            yield event.plain_result("❌ 没有可购买的订单（可能都是你自己的订单）")
            return
        
        # 检查钱包余额
        if player['wallet'] < total_price:
            yield event.plain_result(f"❌ 钱包余额不足（需要¥{total_price:,}，有¥{player['wallet']:,}）")
            return
        
        # 执行购买
        actual_bought = 0
        for order, quantity in orders_to_buy:
            order_price = int(quantity * order['price'])
            
            # 扣除买方货币
            player['wallet'] -= order_price
            
            # 释放卖方的物品中介到买方（只释放购买的数量）
            self.release_escrow(order['escrow_id'], user_id, system, quantity)
            
            # 给卖方钱包加钱
            seller = self.get_player(order['seller_id'])
            seller['wallet'] += order_price
            
            # 更新或删除订单
            if quantity >= order['quantity']:
                self.market_data[system].remove(order)
            else:
                order['quantity'] -= quantity
            
            actual_bought += quantity
        
        self.save_market()
        self.save_players()
        
        # 计算平均价格
        avg_price = int(total_price / actual_bought) if actual_bought > 0 else 0
        
        yield event.plain_result(
            f"✅ 购买成功\n"
            f"📦 {item_name} ×{actual_bought}\n"
            f"💰 总花费：¥{total_price:,}\n"
            f"📊 平均单价：¥{avg_price:,}\n"
            f"📍 已存入{system}机库"
        )

    @filter.command("游戏我的订单")
    async def my_orders(self, event: AstrMessageEvent):
        """查看自己上架的订单"""
        user_id = str(event.get_sender_id())
        
        system = "吉他"
        orders = self.market_data.get(system, [])
        
        my_sell_orders = [o for o in orders if o.get('seller_id') == user_id]
        my_buy_orders = [o for o in orders if o.get('buyer_id') == user_id]
        
        if not my_sell_orders and not my_buy_orders:
            yield event.plain_result("📋 我的订单\n\n暂无上架的订单")
            return
        
        text = "📋 我的订单\n\n"
        
        if my_sell_orders:
            text += "🔴 我的卖单：\n"
            for order in my_sell_orders:
                text += f"  ID:{order['order_id']} {order['item_name']} ×{order['quantity']} ¥{order['price']:,}/单位\n"
            text += "\n"
        
        if my_buy_orders:
            text += "🟢 我的买单：\n"
            for order in my_buy_orders:
                text += f"  ID:{order['order_id']} {order['item_name']} ×{order['quantity']} ¥{order['price']:,}/单位\n"
        
        text += "\n使用 /游戏取消订单 <订单ID> 取消订单"
        yield event.plain_result(text)

    @filter.command("游戏取消订单")
    async def cancel_order(self, event: AstrMessageEvent):
        """取消自己上架的订单"""
        args = event.message_str.split()[1:]
        
        if len(args) < 1:
            yield event.plain_result("❌ 用法：/游戏取消订单 <订单ID>")
            return
        
        order_id = args[0]
        user_id = str(event.get_sender_id())
        player = self.get_player(user_id)
        
        system = "吉他"
        
        # 查找订单
        order = None
        for o in self.market_data.get(system, []):
            if o['order_id'] == order_id:
                order = o
                break
        
        if not order:
            yield event.plain_result(f"❌ 订单 {order_id} 不存在")
            return
        
        # 检查是否是订单所有者
        if order.get('seller_id') != user_id and order.get('buyer_id') != user_id:
            yield event.plain_result("❌ 只能取消自己的订单")
            return
        
        # 返还中介冻结的物品/货币
        escrow = self.escrow_data.get(order['escrow_id'])
        if escrow and escrow['status'] == 'frozen':
            if order['type'] == 'sell':
                # 卖单：返还中介中剩余的物品到机库
                item_name = order['item_name']
                quantity = escrow['quantity']  # 使用中介中剩余的数量
                
                if system not in player['assets']:
                    player['assets'][system] = {"minerals": {}, "ores": {}, "ships": []}
                
                if order.get('item_type') == 'ore' or item_name in self.ORES_DATA:
                    if 'ores' not in player['assets'][system]:
                        player['assets'][system]['ores'] = {}
                    if item_name not in player['assets'][system]['ores']:
                        player['assets'][system]['ores'][item_name] = 0
                    player['assets'][system]['ores'][item_name] += quantity
                else:
                    if 'minerals' not in player['assets'][system]:
                        player['assets'][system]['minerals'] = {}
                    if item_name not in player['assets'][system]['minerals']:
                        player['assets'][system]['minerals'][item_name] = 0
                    player['assets'][system]['minerals'][item_name] += quantity
                    
            elif order['type'] == 'buy':
                # 买单：返还中介中剩余的货币到钱包
                player['wallet'] += escrow['quantity']
            
            escrow['status'] = 'cancelled'
            self.save_escrow()
        
        # 从市场删除订单
        self.market_data[system].remove(order)
        self.save_market()
        self.save_players()
        
        yield event.plain_result(f"✅ 订单已取消\n📋 ID: {order_id}\n📦 {order['item_name']} ×{order['quantity']}\n💰 冻结的{'物品' if order['type'] == 'sell' else '货币'}已返还")