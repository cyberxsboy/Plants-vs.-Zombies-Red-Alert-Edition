# backend/main.py
from flask import Flask
from flask_cors import CORS
from flask import jsonify # 导入 jsonify
import random # 导入 random 模块
import threading # 导入 threading 模块
import time # 导入 time 模块
from flask import request # 导入 request
import heapq # 导入 heapq 模块，用于优先队列

app = Flask(__name__)
CORS(app) # 允许所有源进行跨域请求

class PlayerResources:
    def __init__(self, money=1000, power=500, sun=200):
        self.money = money
        self.power = power
        self.sun = sun

    def to_dict(self):
        return {
            "money": self.money,
            "power": self.power,
            "sun": self.sun
        }

# 初始化玩家资源
game_resources = PlayerResources()

class GameMap:
    def __init__(self, width=30, height=20):
        self.width = width
        self.height = height
        self.grid = self._generate_map()

    def _generate_map(self):
        # 简单的地图生成逻辑：0-草地, 1-矿区, 2-战略要点
        grid = [[0 for _ in range(self.width)] for _ in range(self.height)]
        
        # 随机生成矿区
        for _ in range(self.width * self.height // 10): # 大约10%的矿区
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            grid[y][x] = 1
        
        # 随机生成战略要点
        for _ in range(self.width * self.height // 50): # 大约2%的战略要点
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            grid[y][x] = 2
            
        return grid

    def to_dict(self):
        return {
            "width": self.width,
            "height": self.height,
            "grid": self.grid
        }

class Entity:
    def __init__(self, x, y, health, attack=0, defense=0):
        self.x = x
        self.y = y
        self.health = health
        self.attack = attack
        self.defense = defense

    def take_damage(self, damage):
        actual_damage = max(0, damage - self.defense)
        self.health -= actual_damage
        return self.health <= 0

    def to_dict(self):
        return {
            "x": self.x,
            "y": self.y,
            "health": self.health,
            "attack": self.attack,
            "defense": self.defense,
            "type": self.__class__.__name__
        }

class Unit(Entity):
    def __init__(self, x, y, health, attack, defense, speed):
        super().__init__(x, y, health, attack, defense)
        self.speed = speed

    def to_dict(self):
        data = super().to_dict()
        data["speed"] = self.speed
        return data

class Building(Entity):
    MAX_HEALTH = 100 # 所有建筑的默认最大生命值
    def __init__(self, x, y, health, defense):
        super().__init__(x, y, health, 0, defense) # 建筑通常没有攻击力


class BasicPlant(Building):
    def __init__(self, x, y, health=80, defense=10, attack=15, attack_range=2, sun_cost=75):
        super().__init__(x, y, health, defense)
        self.attack = attack
        self.attack_range = attack_range
        self.sun_cost = sun_cost # 植物的阳光消耗

    def attack_targets(self, units):
        targets_hit = []
        for unit in units:
            if isinstance(unit, Unit) and not isinstance(unit, EngineerZombie): # 攻击僵尸
                distance = ((self.x - unit.x)**2 + (self.y - unit.y)**2)**0.5
                if distance <= self.attack_range:
                    if unit.take_damage(self.attack):
                        targets_hit.append(unit)
                    print(f"Basic Plant at ({self.x},{self.y}) attacked unit at ({unit.x},{unit.y}). New health: {unit.health}")
        return targets_hit

class Headquarters(Building):
    def __init__(self, x, y, health=500, defense=20):
        super().__init__(x, y, health, defense)
        self.MAX_HEALTH = health # 基地有自己的最大生命值

class TeslaCoilPlant(Building):
    def __init__(self, x, y, health=150, defense=15, attack=40, attack_range=4, power_consumption=15):
        super().__init__(x, y, health, defense)
        self.attack = attack
        self.attack_range = attack_range
        self.power_consumption = power_consumption

    def attack_targets(self, units, game_resources):
        if game_resources.power >= self.power_consumption:
            game_resources.power -= self.power_consumption
            print(f"Tesla Coil at ({self.x},{self.y}) consumed {self.power_consumption} power.")
            targets_hit = []
            for unit in units:
                # 假设僵尸是敌方单位
                if isinstance(unit, Unit) and not isinstance(unit, EngineerZombie): # 排除我方工程师僵尸
                    distance = ((self.x - unit.x)**2 + (self.y - unit.y)**2)**0.5
                    if distance <= self.attack_range:
                        if unit.take_damage(self.attack):
                            targets_hit.append(unit) # 记录被击败的单位
                        print(f"Tesla Coil at ({self.x},{self.y}) attacked unit at ({unit.x},{unit.y}). New health: {unit.health}")
            return targets_hit # 返回被击败的单位列表
        return []


class EngineerZombie(Unit):
    def __init__(self, x, y, health=60, attack=8, defense=2, speed=1, repair_amount=25):
        super().__init__(x, y, health, attack, defense, speed)
        self.repair_amount = repair_amount
    
    def repair(self, target_building):
        # 工程师僵尸修复建筑的逻辑
        if target_building.health < target_building.__class__.MAX_HEALTH: # 假设建筑有最大生命值
            target_building.health += self.repair_amount
            if target_building.health > target_building.__class__.MAX_HEALTH:
                target_building.health = target_building.__class__.MAX_HEALTH
            print(f"Engineer Zombie at ({self.x},{self.y}) repaired a building at ({target_building.x},{target_building.y}). New health: {target_building.health}")

class BasicZombie(Unit):
    def __init__(self, x, y, health=40, attack=7, defense=1, speed=1):
        super().__init__(x, y, health, attack, defense, speed)

class FastZombie(Unit):
    def __init__(self, x, y, health=25, attack=5, defense=0, speed=3):
        super().__init__(x, y, health, attack, defense, speed)

# 定义可建造的实体及其成本
AVAILABLE_ENTITIES = {
    "BasicPlant": {"type": "plant", "cost": {"money": 75, "sun": 75}, "description": "基础植物，攻击附近的僵尸。"},
    "TeslaCoilPlant": {"type": "building", "cost": {"money": 250, "power": 25}, "description": "磁暴线圈，消耗电力进行范围攻击。"}
}

class Pathfinding:
    def __init__(self, game_map):
        self.game_map = game_map

    def heuristic(self, a, b):
        # 曼哈顿距离作为启发式函数
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def find_path(self, start, end):
        open_set = []
        heapq.heappush(open_set, (0, start)) # (f_score, node)

        came_from = {}

        g_score = { (x, y): float('inf') for y in range(self.game_map.height) for x in range(self.game_map.width) }
        g_score[start] = 0

        f_score = { (x, y): float('inf') for y in range(self.game_map.height) for x in range(self.game_map.width) }
        f_score[start] = self.heuristic(start, end)

        while open_set:
            current_f_score, current = heapq.heappop(open_set)

            if current == end:
                return self._reconstruct_path(came_from, current)

            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]: # 四个方向
                neighbor = (current[0] + dx, current[1] + dy)

                if not (0 <= neighbor[0] < self.game_map.width and 0 <= neighbor[1] < self.game_map.height):
                    continue # 超出地图范围

                # 临时：目前所有非建筑格子都可通行。后续可根据地形类型设置不同权重
                # if self.game_map.grid[neighbor[1]][neighbor[0]] == SOME_OBSTACLE_TYPE:
                #     continue

                tentative_g_score = g_score[current] + 1 # 假设每一步的成本为1

                if tentative_g_score < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g_score
                    f_score[neighbor] = tentative_g_score + self.heuristic(neighbor, end)
                    if (f_score[neighbor], neighbor) not in open_set:
                        heapq.heappush(open_set, (f_score[neighbor], neighbor))
        
        return None # 没有找到路径

    def _reconstruct_path(self, came_from, current):
        path = []
        while current in came_from:
            path.append(current)
            current = came_from[current]
        path.append(current) # 添加起点
        return path[::-1] # 返回反转后的路径（从起点到终点）

class GameLoop(threading.Thread):
    def __init__(self, game_resources, game_map, interval=1):
        super().__init__()
        self.game_resources = game_resources
        self.game_map = game_map # 添加游戏地图引用
        self.pathfinder = Pathfinding(game_map) # 初始化寻路器
        self.interval = interval # 游戏循环更新间隔（秒）
        self._running = False
        self.units = [] # 所有单位，包括植物和僵尸
        self.buildings = [] # 所有建筑
        self.game_state = "running" # 游戏状态：running, win, lose
        self.game_time = 0 # 游戏时间（秒）
        self.last_zombie_spawn_time = 0 # 上次僵尸生成时间
        self.zombie_spawn_interval = 5 # 僵尸生成间隔（秒）

    def run(self):
        self._running = True
        while self._running:
            self.update_game_state()
            time.sleep(self.interval)

    def stop(self):
        self._running = False

    def update_game_state(self):
        if self.game_state != "running":
            return # 游戏已经结束

        self.game_time += self.interval

        # 胜利条件：游戏进行 120 秒
        if self.game_time >= 120:
            self.game_state = "win"
            print("Game Over: You Win!")
            return

        # 失败条件：基地被摧毁
        if not any(isinstance(b, Headquarters) and b.health > 0 for b in self.buildings):
            self.game_state = "lose"
            print("Game Over: You Lose! Headquarters destroyed.")
            return

        # 资源生成逻辑
        self.game_resources.money += 20 # 每秒增加金钱
        self.game_resources.power += 10  # 每秒增加电力
        self.game_resources.sun += 10 # 每秒增加阳光

        # 僵尸生成逻辑
        if self.game_time - self.last_zombie_spawn_time >= self.zombie_spawn_interval:
            self.last_zombie_spawn_time = self.game_time
            # 随机在地图右侧生成僵尸
            spawn_y = random.randint(0, self.game_map.height - 1)
            zombie_type = random.choice([BasicZombie, FastZombie, EngineerZombie])
            new_zombie = zombie_type(x=self.game_map.width - 1, y=spawn_y)
            self.units.append(new_zombie)
            print(f"Spawned a {zombie_type.__name__} at ({new_zombie.x},{new_zombie.y})")

        # 工程师僵尸修复逻辑 (临时示例)
        for unit in self.units:
            if isinstance(unit, EngineerZombie):
                # 寻找附近受损的建筑进行修复
                for building in self.buildings:
                    # 假设修复范围为1格
                    if abs(unit.x - building.x) <= 1 and abs(unit.y - building.y) <= 1 and building.health < building.MAX_HEALTH: # 使用 Building 类的 MAX_HEALTH
                        unit.repair(building)
                        break # 每次只修复一个建筑

        # 磁暴线圈植物攻击逻辑
        dead_units = []
        for building in self.buildings:
            if isinstance(building, TeslaCoilPlant):
                dead_units.extend(building.attack_targets(self.units, self.game_resources))
            elif isinstance(building, BasicPlant):
                dead_units.extend(building.attack_targets(self.units)) # BasicPlant 不需要消耗电力

        # 僵尸移动逻辑 (简单向前移动)
        for unit in self.units:
            if isinstance(unit, Unit) and not isinstance(unit, EngineerZombie): # 只移动僵尸
                # 使用寻路算法向地图左侧（x=0）移动
                start_pos = (unit.x, unit.y)
                # 寻找地图最左侧的任意一点作为目标 (简化处理，实际游戏中目标会更具体)
                end_pos = (0, unit.y) 
                path = self.pathfinder.find_path(start_pos, end_pos)
                
                if path and len(path) > 1: # 如果找到了路径且路径长度大于1 (不包括当前位置)
                    next_step = path[1] # 路径的下一步
                    unit.x = next_step[0]
                    unit.y = next_step[1]
                    print(f"Zombie at {start_pos} moved to {next_step}")
                else:
                    unit.x -= unit.speed # 如果没有路径，则继续简单向前移动
                    if unit.x < 0:
                        unit.x = 0 # 阻止僵尸移出地图

        # 移除死亡单位
        self.units = [unit for unit in self.units if unit not in dead_units]

        print(f"Game State Updated: Money={self.game_resources.money}, Power={self.game_resources.power}, Sun={self.game_resources.sun}")

    def get_game_state_data(self):
        return {
            "game_state": self.game_state,
            "game_time": self.game_time,
            "units": [unit.to_dict() for unit in self.units],
            "buildings": [building.to_dict() for building in self.buildings],
            "resources": self.game_resources.to_dict()
        }

# 初始化游戏地图
game_map = GameMap()

# 初始化游戏循环
game_loop = GameLoop(game_resources, game_map)

# --- 临时添加测试单位和建筑 ---
# 添加一个工程师僵尸
engineer_zombie = EngineerZombie(x=5, y=5, health=50)
game_loop.units.append(engineer_zombie)

# 添加一个受损的建筑
damaged_building = Building(x=6, y=5, health=50, defense=10)
game_loop.buildings.append(damaged_building)

# 添加一个磁暴线圈植物
tesla_coil = TeslaCoilPlant(x=3, y=3)
game_loop.buildings.append(tesla_coil)

# 添加一个普通僵尸（用于被磁暴线圈攻击）
basic_zombie = BasicZombie(x=4, y=3, health=40)
game_loop.units.append(basic_zombie)

# 添加一个基本植物
basic_plant = BasicPlant(x=8, y=8, health=50)
game_loop.buildings.append(basic_plant)

# 添加一个快速僵尸
fast_zombie = FastZombie(x=10, y=8, health=20)
game_loop.units.append(fast_zombie)

# 添加一个基地
headquarters = Headquarters(x=1, y=self.game_map.height // 2)
game_loop.buildings.append(headquarters)
# --------------------------------

@app.route('/game_state')
def get_game_state():
    return jsonify(game_loop.get_game_state_data())

@app.route('/entities')
def get_entities():
    return jsonify({
        "units": [unit.to_dict() for unit in game_loop.units],
        "buildings": [building.to_dict() for building in game_loop.buildings]
    })

@app.route('/')
def hello_world():
    return 'Hello from Red Alert PvZ backend!'

@app.route('/resources')
def get_resources():
    return jsonify(game_resources.to_dict())

@app.route('/map')
def get_map():
    return jsonify(game_map.to_dict())

@app.route('/start_game')
def start_game():
    if not game_loop._running:
        game_loop.start()
        return "Game loop started."
    return "Game loop is already running."

@app.route('/stop_game')
def stop_game():
    if game_loop._running:
        game_loop.stop()
        return "Game loop stopped."
    return "Game loop is not running."

@app.route('/available_entities')
def get_available_entities():
    return jsonify(AVAILABLE_ENTITIES)

@app.route('/place_entity', methods=['POST'])
def place_entity():
    data = request.get_json()
    entity_type = data.get('entity_type')
    x = data.get('x')
    y = data.get('y')

    if entity_type not in AVAILABLE_ENTITIES:
        return jsonify({"success": False, "message": "Unknown entity type."}), 400

    entity_info = AVAILABLE_ENTITIES[entity_type]
    cost = entity_info["cost"]

    # 检查资源
    if game_resources.money < cost.get("money", 0) or \
       game_resources.power < cost.get("power", 0) or \
       game_resources.sun < cost.get("sun", 0):
        return jsonify({"success": False, "message": "Insufficient resources."}), 400

    # 检查放置位置是否被占用 (简单检查)
    for building in game_loop.buildings:
        if building.x == x and building.y == y:
            return jsonify({"success": False, "message": "Position already occupied."}), 400

    # 扣除资源
    game_resources.money -= cost.get("money", 0)
    game_resources.power -= cost.get("power", 0)
    game_resources.sun -= cost.get("sun", 0)

    # 创建实体并添加到游戏循环中
    new_entity = None
    if entity_type == "BasicPlant":
        new_entity = BasicPlant(x=x, y=y)
        game_loop.buildings.append(new_entity)
    elif entity_type == "TeslaCoilPlant":
        new_entity = TeslaCoilPlant(x=x, y=y)
        game_loop.buildings.append(new_entity)
    # 可以添加更多单位类型...

    if new_entity:
        return jsonify({"success": True, "message": f"{entity_type} placed at ({x},{y})."}), 200
    return jsonify({"success": False, "message": "Failed to place entity."}), 500

if __name__ == '__main__':
    app.run(debug=True)
