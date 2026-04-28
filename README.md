# 慢病用药小管家

这是一个真正可运行的 Flask + SQLite 网页应用，包含：

- 用户注册 / 登录 / 退出
- SQLite 数据库存储
- 添加、删除用药计划
- 今日用药任务
- 服药打卡
- 漏服记录
- 药品库存自动减少
- 库存不足预警
- 复诊续方倒计时
- 复诊沟通话术生成
- 最近 7 天服药记录
- 本地数据库持久化保存

## 一、在本地运行

进入项目文件夹：

```bash
cd chronic_medicine_manager
```

创建虚拟环境：

```bash
python -m venv .venv
```

激活虚拟环境：

macOS / Linux：

```bash
source .venv/bin/activate
```

Windows：

```bash
.venv\Scripts\activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

启动项目：

```bash
python app.py
```

浏览器打开：

```text
http://127.0.0.1:5000
```

## 二、数据库说明

数据库文件会自动生成在项目根目录：

```text
medicine_manager.db
```

你注册的账号、添加的药品、打卡记录都会保存到这个数据库里。

## 三、生成可以提交的公网链接

本项目在本地运行后，可以用 ngrok / localtunnel / frp 等工具映射成公网链接。

以 ngrok 为例：

```bash
ngrok http 5000
```

然后复制生成的 https 链接提交即可。

注意：本地电脑和 Flask 服务必须保持运行，链接才可以访问。


## 四、Render 免费部署步骤

本版本已经适配 Render + SQLite。

### 1. 上传到 GitHub

在 GitHub 新建一个仓库，例如：

```text
chronic-medicine-manager
```

把本项目文件夹里的所有文件上传进去。

注意：项目根目录应该直接能看到这些文件：

```text
app.py
requirements.txt
render.yaml
Procfile
templates/
static/
```

不要把整个压缩包上传进去。

### 2. 在 Render 创建 Web Service

进入 Render 后：

1. New
2. Web Service
3. Connect GitHub repository
4. 选择你刚刚上传的仓库

Render 会自动识别 render.yaml。若需要手动填写，使用：

```text
Build Command:
pip install -r requirements.txt

Start Command:
gunicorn app:app
```

### 3. 等待部署完成

部署成功后，Render 会给你一个公网链接，例如：

```text
https://chronic-medicine-manager.onrender.com
```

这个链接可以直接提交。

### 4. SQLite 注意事项

本项目使用 SQLite 文件数据库。Render 免费实例重启或重新部署时，数据库文件可能会丢失或重置。用于比赛演示和短期提交没有问题。正式长期使用建议升级 PostgreSQL。
