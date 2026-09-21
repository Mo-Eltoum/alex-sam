build-AlexDepsLayer:
	mkdir -p "$(ARTIFACTS_DIR)/python"
	python3 -m pip install -r requirements.txt -t "$(ARTIFACTS_DIR)/python"
	rm -rf "$(ARTIFACTS_DIR)/python/bin" "$(ARTIFACTS_DIR)/python/*.dist-info" || true
	cp -R src "$(ARTIFACTS_DIR)/python/src"
