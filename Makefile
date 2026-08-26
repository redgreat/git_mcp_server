.PHONY: release

# ============ 发布与部署 ============
release: ## 发布版本（自动递增版本号并推送标签触发构建）
ifeq ($(OS),Windows_NT)
	@pwsh -NoProfile -ExecutionPolicy Bypass -Command "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; Write-Host 'Release tag push...'"
	@pwsh -NoProfile -ExecutionPolicy Bypass -File script/release.ps1
else
	@echo "Release tag push..."
	@bash script/release.sh
endif