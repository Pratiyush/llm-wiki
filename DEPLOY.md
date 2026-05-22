# LLM-Wiki Windows 服务器部署指南

## 环境要求

- Windows Server 2016+ 或 Windows 10/11
- Python 3.12+（https://www.python.org/downloads/）
- 内网可达

## 第一步：安装 Python

1. 下载 Python 3.12+ 安装包
2. 安装时 **勾选 "Add Python to PATH"**
3. 打开命令提示符验证：
   ```
   python --version
   ```

## 第二步：复制项目

将整个 `llm-wiki` 文件夹复制到服务器，例如 `D:\llm-wiki`。

## 第三步：安装依赖

打开命令提示符，进入项目目录：
```
cd D:\llm-wiki
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[web]"
```

## 第四步：配置环境变量

在项目根目录创建 `.env` 文件，填入以下内容：

```env
# 智谱 GLM API
ZAI_API_KEY=你的智谱API密钥
ZAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
ZAI_MODEL_FLASH=glm-4-flash
ZAI_MODEL_PRO=gear-01

# DeepSeek API
DEEPSEEK_API_KEY=你的DeepSeek密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# Kimi API（可选）
KIMI_API_KEY=
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL=kimi-k2-0711

# JWT 密钥（随意填写一个长随机字符串）
JWT_SECRET_KEY=请替换为一个随机字符串
```

## 第五步：启动服务

### 方式一：使用启动脚本（推荐）

双击 `start.bat` 即可。

### 方式二：手动启动

```
cd D:\llm-wiki
.venv\Scripts\activate
python -m llmwiki web --host 0.0.0.0 --port 8765
```

### Notebook 知识库升级

如果是从旧版企业制度知识库升级到 notebook 版本，请先执行一次默认知识库迁移：

```
python -m llmwiki notebooks migrate-default
```

迁移会把原有 `wiki/` 和 `raw/` 内容复制到默认 notebook **「企业管理制度」** 下，不覆盖已存在文件。

## 第六步：防火墙放行

1. 打开 **Windows 防火墙** → **高级设置**
2. 点击 **入站规则** → **新建规则**
3. 选择 **端口** → **TCP** → **特定本地端口** 输入 `8765`
4. 选择 **允许连接** → 勾选 **域** 和 **专用**
5. 命名为 "LLM-Wiki"

或使用命令（管理员权限）：
```
netsh advfirewall firewall add rule name="LLM-Wiki" dir=in action=allow protocol=TCP localport=8765
```

## 第七步：创建管理员

1. 在服务器或局域网电脑上打开浏览器，访问 `http://服务器IP:8765`
2. 点击右上角 **登录** 按钮
3. 点击 **注册**，填写第一个用户（第一个注册的用户自动成为 admin）
4. 登录后，在 **管理** 标签页可以创建其他用户并分配角色

## 第八步：创建其他用户

管理员登录后，在管理标签页可以看到用户管理功能。

用户角色说明：
| 角色 | 问答 | 保存到Wiki | 管理 |
|------|------|-----------|------|
| admin（管理员） | ✓ | 直接写入 | 全部 |
| leader（部门长） | ✓ | 直接写入 | 审批 |
| staff（普通员工） | ✓ | 提交审批 | 统计 |

---

## 本地一键部署到腾讯云

本项目包含 `deploy.py`，用于从本机增量上传代码和知识库到腾讯云服务器 `121.4.89.177`，并重启 `llmwiki` systemd 服务。脚本不会删除服务器上的文件，避免误删 Web UI 上传的资料。

建议通过环境变量提供 SSH 密码：

```
$env:LLMWIKI_DEPLOY_PASSWORD="服务器密码"
python deploy.py
```

如果未设置 `LLMWIKI_DEPLOY_PASSWORD`，脚本会在运行时提示输入密码。部署过程中会自动执行 `python -m llmwiki notebooks migrate-default`，确保旧版企业制度知识库进入默认 notebook。

---

## 可选：注册为 Windows 服务（开机自启）

使用 [NSSM](https://nssm.cc/) 将应用注册为 Windows 服务，实现开机自动启动、崩溃自动重启。

### 安装 NSSM

1. 从 https://nssm.cc/download 下载 nssm.exe
2. 放到 `C:\Windows\` 或其他 PATH 目录下

### 注册服务

打开命令提示符（管理员权限）：

```
cd D:\llm-wiki
nssm install LLMWiki
```

在弹出的窗口中填写：

- **Path**: `D:\llm-wiki\.venv\Scripts\python.exe`
- **Arguments**: `-m llmwiki web --host 0.0.0.0 --port 8765`
- **Startup directory**: `D:\llm-wiki`

切换到 **I/O** 标签页：
- **Output (stdout)**: `D:\llm-wiki\service.log`
- **Error (stderr)**: `D:\llm-wiki\error.log`

点击 **Install service**。

### 管理服务

```
nssm start LLMWiki      # 启动
nssm stop LLMWiki        # 停止
nssm restart LLMWiki     # 重启
nssm status LLMWiki      # 查看状态
nssm remove LLMWiki      # 删除服务
```

---

## 常见问题

### Q: 其他电脑无法访问？
1. 确认服务已启动（服务器上能访问 http://localhost:8765）
2. 确认防火墙已放行 8765 端口
3. 确认两台电脑在同一网段（能互相 ping 通）

### Q: 如何查看服务器 IP？
```
ipconfig
```
找到以太网适配器下的 IPv4 地址，如 `192.168.1.100`。

### Q: 如何更换端口？
修改 `start.bat` 或启动命令中的 `--port` 参数，同时更新防火墙规则。

### Q: 数据库在哪里？
SQLite 数据库文件在项目根目录的 `llmwiki.db`，可直接备份。

### Q: 知识库文档在哪里？
`wiki/` 目录下的 `.md` 文件。上传的文档经过处理后存放在 `wiki/sources/` 下。
