# 发布到 GitHub（维护者）

仓库地址：https://github.com/shutiao165-tech/social-ecom-monthly-report

## 推送前检查清单

- [ ] `.env` 未纳入版本库
- [ ] `~/.config/tikhub/key` 未纳入
- [ ] `data/` 下无真实 `merged_raw.json` / `analysis.json`
- [ ] HTML 中无秒搭 / 飞书内网链接
- [ ] 无真实姓名、工号、内部 wiki token
- [ ] `templates/brief/` 无内部 SKU 表
- [ ] `git grep -E 'henaichishuge|kttfkmbfmy|aiforce'` 无命中

## 首次上传

```bash
cd ~/Desktop/AI_cursor/share/social-ecom-monthly-report

git init
git add .
git status   # 再确认一遍清单
git commit -m "$(cat <<'EOF'
发布双平台爆款月报 Skill

含 TikHub 双池流水线、竞品动作板、scene_links 与 Cursor Skill。
EOF
)"

git branch -M main
git remote add origin https://github.com/shutiao165-tech/social-ecom-monthly-report.git
git push -u origin main
```

## 使用 GitHub CLI（推荐）

```bash
gh auth login          # 若 token 过期：gh auth refresh -h github.com
gh repo create shutiao165-tech/social-ecom-monthly-report --public \
  --source=. --remote=origin --push \
  --description "XHS + Douyin monthly viral report with Cursor Skill (TikHub)"
```

若仓库已存在，只需：

```bash
git remote add origin https://github.com/shutiao165-tech/social-ecom-monthly-report.git
git push -u origin main
```

## 发 Release（可选）

```bash
git tag v1.0.0
git push origin v1.0.0
gh release create v1.0.0 --title "v1.0.0" --notes "方案 C 双池月报首版开源"
```

## 安装 Skill 的用户侧

```bash
git clone https://github.com/shutiao165-tech/social-ecom-monthly-report.git ~/social-ecom-monthly-report
cp -R ~/social-ecom-monthly-report/cursor-skills/social-ecom-monthly-report ~/.cursor/skills/
```

与 [dingtalk-stock-watch](https://github.com/shutiao165-tech/dingtalk-stock-watch) 相同：Skill 放在 `cursor-skills/`，用户复制到 `~/.cursor/skills/`。
