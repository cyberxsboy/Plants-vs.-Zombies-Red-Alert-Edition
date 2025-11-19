// frontend/src/index.ts
console.log("Hello from Red Alert PvZ frontend!");

const canvas = document.getElementById('game-canvas') as HTMLCanvasElement;
const ctx = canvas.getContext('2d');
const entityList = document.getElementById('entity-list') as HTMLElement;
const gameMessageDiv = document.getElementById('game-message') as HTMLElement;
const gameMessageHeader = gameMessageDiv.querySelector('h2') as HTMLElement;
const backgroundMusic = document.getElementById('background-music') as HTMLAudioElement;

const TILE_SIZE = 32; // 每个瓦片的大小

let selectedEntityType: string | null = null;

let cameraOffsetX = 0;
let cameraOffsetY = 0;
let isDragging = false;
let lastPointerX = 0;
let lastPointerY = 0;

async function testBackendConnection() {
    try {
        const response = await fetch('http://127.0.0.1:5000/'); // Flask 默认运行在 5000 端口
        const data = await response.text();
        console.log("Backend Response:", data);
    } catch (error) {
        console.error("Error connecting to backend:", error);
    }
}

async function updateResources() {
    try {
        const response = await fetch('http://127.0.0.1:5000/resources');
        const resources = await response.json();

        (document.getElementById('money') as HTMLElement).innerText = resources.money;
        (document.getElementById('power') as HTMLElement).innerText = resources.power;
        (document.getElementById('sun') as HTMLElement).innerText = resources.sun;

    } catch (error) {
        console.error("Error fetching resources:", error);
    }
}

// 获取可用实体并渲染到 UI
async function loadAvailableEntities() {
    try {
        const response = await fetch('http://127.0.0.1:5000/available_entities');
        const entities = await response.json();

        entityList.innerHTML = ''; // 清空现有列表
        for (const entityName in entities) {
            const entityInfo = entities[entityName];
            const entityItem = document.createElement('div');
            entityItem.classList.add('entity-item');
            entityItem.dataset.entityType = entityName;
            entityItem.innerHTML = `
                <div class="entity-icon"></div>
                <div class="entity-details">
                    <p><strong>${entityName}</strong></p>
                    <p class="cost">金钱: ${entityInfo.cost.money || 0}, 电力: ${entityInfo.cost.power || 0}, 阳光: ${entityInfo.cost.sun || 0}</p>
                    <p>${entityInfo.description}</p>
                </div>
            `;
            entityItem.addEventListener('click', () => {
                if (selectedEntityType === entityName) {
                    selectedEntityType = null;
                    entityItem.classList.remove('selected');
                } else {
                    selectedEntityType = entityName;
                    // 移除其他已选择的样式
                    document.querySelectorAll('.entity-item').forEach(item => {
                        item.classList.remove('selected');
                    });
                    entityItem.classList.add('selected');
                }
                // 重新绘制以显示/隐藏虚影
                drawMap();
            });
            entityList.appendChild(entityItem);
        }
    } catch (error) {
        console.error("Error loading available entities:", error);
    }
}

async function drawMap() {
    if (!ctx) return;

    try {
        const response = await fetch('http://127.0.0.1:5000/map');
        const mapData = await response.json();

        canvas.width = mapData.width * TILE_SIZE;
        canvas.height = mapData.height * TILE_SIZE;

        // 保存当前上下文状态
        ctx.save();
        // 应用相机偏移
        ctx.translate(cameraOffsetX, cameraOffsetY);

        for (let y = 0; y < mapData.height; y++) {
            for (let x = 0; x < mapData.width; x++) {
                const tileType = mapData.grid[y][x];
                let color = '#00FF00'; // 默认草地
                if (tileType === 1) {
                    color = '#8B4513'; // 矿区
                } else if (tileType === 2) {
                    color = '#FFD700'; // 战略要点
                }
                ctx.fillStyle = color;
                ctx.fillRect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE);
                ctx.strokeStyle = '#333';
                ctx.strokeRect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE);
            }
        }

        // 绘制单位和建筑
        const entitiesResponse = await fetch('http://127.0.0.1:5000/entities');
        const entitiesData = await entitiesResponse.json();

        // 绘制建筑
        for (const building of entitiesData.buildings) {
            let buildingColor = '#0000FF'; // 默认蓝色表示我方建筑
            if (building.type === "Headquarters") {
                buildingColor = '#FF0000'; // 基地为红色
            } else if (building.type === "TeslaCoilPlant") {
                buildingColor = '#FFFF00'; // 磁暴线圈为黄色
            } else if (building.type === "BasicPlant") {
                buildingColor = '#008000'; // 基础植物为深绿色
            }
            ctx.fillStyle = buildingColor;
            ctx.fillRect(building.x * TILE_SIZE, building.y * TILE_SIZE, TILE_SIZE, TILE_SIZE);
            ctx.strokeStyle = '#FFF';
            ctx.strokeRect(building.x * TILE_SIZE, building.y * TILE_SIZE, TILE_SIZE, TILE_SIZE);

            // 显示生命值 (简单文本)
            ctx.fillStyle = "#FFF";
            ctx.font = "10px Arial";
            ctx.fillText(building.health.toString(), building.x * TILE_SIZE + TILE_SIZE / 4, building.y * TILE_SIZE + TILE_SIZE / 2);
        }

        // 绘制单位（僵尸）
        for (const unit of entitiesData.units) {
            let unitColor = '#800080'; // 默认紫色表示僵尸
            if (unit.type === "EngineerZombie") {
                unitColor = '#FFA500'; // 工程师僵尸为橙色
            } else if (unit.type === "FastZombie") {
                unitColor = '#ADD8E6'; // 快速僵尸为浅蓝色
            }
            ctx.fillStyle = unitColor;
            ctx.beginPath();
            ctx.arc(unit.x * TILE_SIZE + TILE_SIZE / 2, unit.y * TILE_SIZE + TILE_SIZE / 2, TILE_SIZE / 2 - 2, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = '#FFF';
            ctx.stroke();

            // 显示生命值 (简单文本)
            ctx.fillStyle = "#FFF";
            ctx.font = "10px Arial";
            ctx.fillText(unit.health.toString(), unit.x * TILE_SIZE + TILE_SIZE / 4, unit.y * TILE_SIZE + TILE_SIZE / 2);
        }

        // 绘制虚影
        if (selectedEntityType && mouseX !== undefined && mouseY !== undefined) {
            // 虚影位置需要考虑相机偏移
            const gridX = Math.floor((mouseX - cameraOffsetX) / TILE_SIZE);
            const gridY = Math.floor((mouseY - cameraOffsetY) / TILE_SIZE);
            
            ctx.fillStyle = "rgba(255, 255, 255, 0.5)"; // 半透明白色虚影
            ctx.fillRect(gridX * TILE_SIZE, gridY * TILE_SIZE, TILE_SIZE, TILE_SIZE);
        }

        // 恢复上下文状态，以便其他绘制不受偏移影响
        ctx.restore();

    } catch (error) {
        console.error("Error fetching or drawing map:", error);
    }
}

// 获取游戏状态并显示消息
async function updateGameState() {
    try {
        const response = await fetch('http://127.0.0.1:5000/game_state');
        const gameState = await response.json();

        if (gameState.state !== "running") {
            gameMessageHeader.innerText = gameState.state === "win" ? "你赢了！" : "你输了！";
            gameMessageDiv.style.display = "block";
            // 停止所有游戏更新
            await fetch('http://127.0.0.1:5000/stop_game');
        }

    } catch (error) {
        console.error("Error fetching game state:", error);
    }
}

// 重新开始游戏（由按钮调用）
function restartGame() {
    gameMessageDiv.style.display = "none";
    // 需要刷新页面或重新初始化后端游戏状态
    location.reload(); 
}

// 将 restartGame 函数暴露给全局作用域，以便 HTML 能够调用
(window as any).restartGame = restartGame;

// 播放背景音乐
function playBackgroundMusic() {
    if (backgroundMusic) {
        backgroundMusic.volume = 0.5; // 设置音量
        backgroundMusic.play().catch(error => {
            console.log("自动播放背景音乐失败，可能需要用户交互", error);
            // 提示用户点击屏幕来播放音乐
            document.body.addEventListener('click', () => {
                backgroundMusic.play();
            }, { once: true });
        });
    }
}

// 播放音效 (占位符)
function playSoundEffect(effect: string) {
    const audio = new Audio(`./audio/${effect}.mp3`);
    audio.volume = 0.7;
    audio.play();
}

// 处理鼠标移动事件以更新虚影位置
let mouseX: number | undefined;
let mouseY: number | undefined;
canvas.addEventListener('mousemove', (e) => {
    mouseX = e.offsetX;
    mouseY = e.offsetY;
    if (selectedEntityType && !isDragging) { // 只有在没有拖动时才更新虚影
        drawMap(); // 重新绘制地图以更新虚影位置
    }
});

// 处理鼠标拖动事件
canvas.addEventListener('pointerdown', (e) => {
    isDragging = true;
    lastPointerX = e.clientX;
    lastPointerY = e.clientY;
    canvas.setPointerCapture(e.pointerId);
});

canvas.addEventListener('pointermove', (e) => {
    if (!isDragging) return;

    const dx = e.clientX - lastPointerX;
    const dy = e.clientY - lastPointerY;

    cameraOffsetX += dx;
    cameraOffsetY += dy;

    lastPointerX = e.clientX;
    lastPointerY = e.clientY;

    drawMap();
});

canvas.addEventListener('pointerup', () => {
    isDragging = false;
});

canvas.addEventListener('mouseleave', () => {
    mouseX = undefined;
    mouseY = undefined;
    if (selectedEntityType && !isDragging) {
        drawMap(); // 移除虚影
    }
});

// 处理点击事件以放置实体
canvas.addEventListener('click', async (e) => {
    if (selectedEntityType && mouseX !== undefined && mouseY !== undefined) {
        // 放置位置需要考虑相机偏移
        const gridX = Math.floor((mouseX - cameraOffsetX) / TILE_SIZE);
        const gridY = Math.floor((mouseY - cameraOffsetY) / TILE_SIZE);

        try {
            const response = await fetch('http://127.0.0.1:5000/place_entity', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    entity_type: selectedEntityType,
                    x: gridX,
                    y: gridY
                })
            });
            const result = await response.json();
            if (result.success) {
                console.log(result.message);
                playSoundEffect('place_building'); // 播放放置音效
                // 放置成功后，清除选择并重新绘制地图和资源
                selectedEntityType = null;
                document.querySelectorAll('.entity-item').forEach(item => {
                    item.classList.remove('selected');
                });
                drawMap();
                updateResources();
            } else {
                alert(result.message);
            }
        } catch (error) {
            console.error("Error placing entity:", error);
            alert("放置实体时发生错误。");
        }
    }
});

testBackendConnection();
loadAvailableEntities(); // 加载可用实体
updateResources(); // 初始加载时更新资源
drawMap(); // 初始加载时绘制地图
updateGameState(); // 初始加载时获取游戏状态
playBackgroundMusic(); // 播放背景音乐

setInterval(updateResources, 1000);
setInterval(updateGameState, 1000); // 每秒更新一次游戏状态
