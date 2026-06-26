# crm-agent Linux 服务器部署指南（直连模式 / 不用 Nginx）

如果不使用 Nginx 作为反向代理，可以直接通过 FastAPI (Uvicorn) 监听公网 IP 端口。
以下是针对**直连模式**的精简部署方案：

---

## 第一步：上传项目代码

将本地的 `crm-agent` 整个文件夹上传至 Linux 服务器的指定工作目录（例如 `/home/ubuntu/crm-agent`）。
可以使用 `scp`、`sftp` 或通过 Git 仓库拉取代码。

---

## 第二步：安装 Python 3 环境与系统依赖

以 Ubuntu/Debian 系统为例：

```bash
# 1. 更新系统包索引
sudo apt update

# 2. 安装 Python3, python3-pip 及虚拟环境支持包
sudo apt install -y python3 python3-pip python3-venv
```

---

## 第三步：创建虚拟环境并安装依赖

进入服务器的项目根目录下：

```bash
cd /home/ubuntu/crm-agent

# 1. 创建虚拟环境
python3 -m venv .venv

# 2. 激活虚拟环境
source .venv/bin/activate

# 3. 升级 pip 并安装依赖
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 第四步：修改配置文件环境 (.env) —— 📢 关键步骤

从模板拷贝并编辑 `.env` 文件：

```bash
cp .env.template .env
nano .env  # 或者使用 vim .env
```

**在直连模式下，请务必进行如下设置**：
```ini
DASHSCOPE_API_KEY=您的生产DashScope密钥
GO_BACKEND_URL=http://your-go-backend-ip:8080

# 📢 必须设为 0.0.0.0，表示监听网卡的所有 IP，只设为 127.0.0.1 会导致外网无法访问
AGENT_HOST=0.0.0.0
AGENT_PORT=8081  # 暴露给小程序的公网访问端口
AGENT_RELOAD=0   # 生产环境关闭热重载，提升运行效率
```

---

## 第五步：开启防火墙/安全组端口 —— 📢 关键步骤

如果不使用 Nginx，客户端（如小程序）需要直接连接您的端口（如 `8081`）。请确保系统防火墙和云服务器提供商的安全组放行了该端口：

### 1. 开启服务器防火墙端口
*   **Ubuntu / Debian (使用 ufw)**：
    ```bash
    sudo ufw allow 8081/tcp
    sudo ufw reload
    ```
*   **CentOS / RHEL (使用 firewalld)**：
    ```bash
    sudo firewall-cmd --zone=public --add-port=8081/tcp --permanent
    sudo firewall-cmd --reload
    ```

### 2. 配置云平台安全组
如果您使用的是阿里云、腾讯云、AWS 等云平台，请登录控制台，进入**云服务器的安全组规则配置**中：
*   **新增入站规则**：允许 **TCP 协议**，端口为 **8081**（或您在 `.env` 中指定的端口），源 IP 设为 **0.0.0.0/0**（允许所有 IP 访问）。

---

## 第六步：使用 Systemd 进行后台守护运行

为了保证服务在后台持续运行、系统重启后自动拉起：

1.  **创建 Service 配置文件**：
    ```bash
    sudo nano /etc/systemd/system/crm-agent.service
    ```
2.  **粘贴并修改以下内容**（注意根据您的实际用户名和项目路径调整 `User`, `WorkingDirectory` 和 `ExecStart`）：
    ```ini
    [Unit]
    Description=CRM Agent FastAPI Service
    After=network.target

    [Service]
    User=ubuntu
    WorkingDirectory=/home/ubuntu/crm-agent
    ExecStart=/home/ubuntu/crm-agent/.venv/bin/python main.py
    Restart=always
    RestartSec=5
    Environment=PYTHONUNBUFFERED=1

    [Install]
    WantedBy=multi-user.target
    ```
3.  **启动服务并设置开机自启**：
    ```bash
    # 重新加载 Systemd 配置
    sudo systemctl daemon-reload

    # 启动 crm-agent 服务
    sudo systemctl start crm-agent

    # 设置开机自动运行
    sudo systemctl enable crm-agent

    # 检查服务状态
    sudo systemctl status crm-agent
    ```

---

## 常用运维指令

*   **查看智能体实时运行日志**：
    ```bash
    sudo journalctl -u crm-agent.service -f
    ```
*   **重启智能体服务**：
    ```bash
    sudo systemctl restart crm-agent
    ```
*   **停止智能体服务**：
    ```bash
    sudo systemctl stop crm-agent
    ```
