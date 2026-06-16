# 发布到 GitHub（维护者）

仓库：https://github.com/shutiao165-tech/social-ecom-monthly-report

## 推送前检查

- [ ] `config/niche_config.py` 未纳入（仅有 `niche_config.example.py`）
- [ ] `.env` / TikHub key 未纳入
- [ ] `data/` 无真实 JSON
- [ ] `git grep -E 'kttfkmbfmy|aiforce|henaichishuge|网易严选|家清'` 无命中

## 首次上传

```bash
cd share/social-ecom-monthly-report

git add .
git status
git commit -m "$(cat <<'EOF'
Refactor: generic brand viral monthly report model

Architecture-only open source; niche/brand via config/niche_config.py.
EOF
)"

git branch -M main
gh auth login   # 若 token 过期
gh repo create shutiao165-tech/social-ecom-monthly-report --public \
  --source=. --remote=origin --push \
  --description "XHS+Douyin brand content viral monthly report (architecture & model)"
```

## Skill 安装名

用户复制：`cursor-skills/brand-viral-monthly-report` → `~/.cursor/skills/brand-viral-monthly-report`

与 [dingtalk-stock-watch](https://github.com/shutiao165-tech/dingtalk-stock-watch) 相同发布范式。
