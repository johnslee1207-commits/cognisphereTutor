# cognisphereTutor AWS 初学者使用指南

这份文档面向普通学习者：你只需要下载 `cognisphereTutor` 这个项目，就可以开始 AWS 初级认证学习。AWS 学习课程包已经随项目提供，不需要再下载 Cognisphere、CognisphereLearningPlugins，或额外收集 AWS 原始资料。

## 你会得到什么

- 一个本地运行的学习网站
- 内置 AWS Certification 学习课程
- 可继续学习的 Learning Path
- 每节课后的 Quick Quiz
- 进度会保存在本机

当前内置 AWS 课程包含 6 个模块、46 个学习目标，适合从零开始准备 AWS Cloud Practitioner / 初级云认证相关内容。

## 一、准备电脑环境

请先安装：

- Git
- Python 3.11 或更新版本
- Node.js 20 或更新版本

在 Windows 上可以打开 PowerShell 检查：

```powershell
git --version
python --version
node --version
npm --version
```

如果这些命令都能显示版本号，就可以继续。

## 二、下载项目

选择一个你希望保存项目的位置，例如 `D:\Projects`：

```powershell
cd D:\Projects
git clone https://github.com/johnslee1207-commits/cognisphereTutor.git
cd cognisphereTutor
```

如果你使用的是官方主仓库，也可以把上面的 GitHub 地址替换为官方仓库地址。

## 三、安装 Tutor

在项目目录中运行：

```powershell
python -m pip install -e .
```

第一次安装可能需要几分钟。安装完成后，初始化本地配置：

```powershell
cognispheretutor init
```

## 四、启动 Tutor

继续在项目目录中运行：

```powershell
cognispheretutor start
```

启动后，终端会显示本地访问地址。默认是：

```text
http://127.0.0.1:3782
```

用浏览器打开这个地址。

如果你只想直接进入学习空间，可以打开：

```text
http://127.0.0.1:3782/space/learning
```

## 五、第一次添加 AWS 课程

进入 `Learning Space` 后：

1. 找到左侧的 `课程库`
2. 找到 `AWS Certification`
3. 点击 `添加课程`
4. 等待学习路径生成
5. 点击 `继续学习`

你也可以在输入框里写：

```text
我是 AWS 新手，想从零开始准备初级认证
```

然后点击：

```text
生成学习路径
```

Tutor 会匹配内置 AWS 课程包，并生成可继续学习的路径。

## 六、开始学习

进入 AWS 学习路径后，建议按照系统安排一步一步学习：

1. 先阅读当前小节内容
2. 完成课后的 Quick Quiz
3. 如果答错，查看解释后再继续
4. 系统会推进到下一节

直接学习页面通常是：

```text
http://127.0.0.1:3782/home/csphere-aws_certification?capability=mastery_path
```

如果页面还没有生成 AWS 学习路径，请先回到：

```text
http://127.0.0.1:3782/space/learning
```

添加 AWS 课程。

## 七、是否需要下载 AWS 原始资料

不需要。

这个 repo 已经包含 AWS 学习课程包：

```text
cognispheretutor/integrations/cognisphere/bundled_packs/aws_certification_bundle.json
```

普通用户只下载并运行 `cognisphereTutor`，就可以开始 AWS 学习。

## 八、是否需要安装 CognisphereLearningPlugins

不需要。

Tutor 会优先使用外部插件仓库，但外部仓库不是普通用户学习 AWS 的必要条件：

- 如果没有外部插件仓库：使用 Tutor 内置课程包
- 如果有外部插件仓库：优先使用外部插件包

普通用户只需要第一种方式。

## 九、学习进度保存在哪里

学习进度保存在本机项目工作区中，通常在：

```text
data/user/workspace/learning/
```

只要你不删除这个目录，学习进度会保留。升级代码后，通常仍然可以继续之前的学习。

如果你想完全从头开始，可以在界面中使用“重新开始/重置进度”相关功能；不要手动删除文件，除非你明确知道自己要清空所有学习记录。

## 十、常见问题

### 打不开页面

确认 `cognispheretutor start` 仍在运行。不要关闭启动 Tutor 的终端窗口。

### 端口被占用

如果提示端口已被占用，先关闭之前启动的 Tutor，或重启电脑后再运行：

```powershell
cognispheretutor start
```

### 页面里没有 AWS 课程

请确认你下载的是包含 bundled packs 的版本。项目中应该存在：

```text
cognispheretutor/integrations/cognisphere/bundled_packs/aws_certification_bundle.json
```

如果文件不存在，请更新项目：

```powershell
git pull
```

然后重新启动 Tutor。

### 模型没有回复或回复很慢

需要在 Tutor 的 `Settings -> Models` 中配置一个可用模型。你可以使用云端模型，也可以配置本地 Ollama。模型负责讲解和互动，AWS 课程结构和学习目标来自本地课程包。

## 十一、推荐的第一次学习流程

1. 启动 Tutor
2. 打开 `http://127.0.0.1:3782/space/learning`
3. 添加 `AWS Certification`
4. 点击 `继续学习`
5. 输入：`我是新手，请从第一课开始`
6. 阅读小课
7. 完成 Quick Quiz
8. 继续下一课

这样就可以开始完整的 AWS 初级认证学习流程。
