# DriftKB

DriftKB 是一个早期阶段的本地 Python CLI，用来在代码变化后检查
Markdown 知识库是否已经过期、无法验证或缺少覆盖。

它面向把架构说明、业务规则、集成约束、运维假设写在 Markdown 里的
工程团队，尤其适合 AI 辅助开发场景：AI 和新人都会把仓库文档当作上下文，
但这些文档可能已经不再真实。

## 安装

发布到 PyPI 后：

```text
pipx install driftkb
uv tool install driftkb
```

从源码安装：

```text
git clone https://github.com/lliangcol/driftkb.git
cd driftkb
python -m pip install -e ".[dev]"
```

## 最小示例

```text
cd examples/minimal
driftkb validate
```

第一次应输出 `DriftKB: PASS`。

然后修改 `src/payment.py`，把：

```python
PAYMENT_PROVIDER = "stripe"
```

改成其他值，再运行：

```text
driftkb validate
```

这次应得到 `FAIL`，因为 KB 中的机械断言已经和代码不一致。

## 常用命令

```text
driftkb init
driftkb validate
driftkb fingerprints update --all
driftkb fingerprints update --all --accept-current
driftkb gaps detect
driftkb promote docs/kb/generated/payment-service-stub.md
driftkb hooks install pre-push
driftkb hooks install pre-commit --strict --no-verify
```

默认 hook 只调用 `driftkb validate`。`driftkb gaps detect` 是手动
advisory 命令，不进入默认 hook 门禁。`--accept-current` 只应在人工确认
当前代码和 KB 一致后使用，它会把选中的 curated KB 基线推进到当前 `HEAD`。

## 安全边界

Verify blocks 会执行仓库 Markdown 中的受限命令。请把它们当作脚本或测试来审查：

- 只在可信仓库中运行 DriftKB。
- 接入 CI 前先审查 `.driftkb/config.yml` 和 KB verify blocks。
- 审查不可信变更时使用 `driftkb validate --no-verify`。
- `last_verified_commit` 应使用固定 commit SHA，不要使用 `HEAD` 或分支名。
- DriftKB core 不依赖 MCP、托管服务、数据库或后台 worker。

## 文档

- [英文 README](README.md)
- [Quickstart](docs/quickstart.md)
- [Concepts](docs/concepts.md)
- [Profiles](docs/profiles.md)
- [Roadmap](docs/roadmap.md)

## License

Apache-2.0.
