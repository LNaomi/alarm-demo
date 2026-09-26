.PHONY: install test report demo clean

install:
	python3 -m pip install -r requirements.txt

test:
	python3 -m pytest

report:
	python3 -m alarm_monitor --count 200 --output reports/report.html

demo: test report
	@echo "打开 reports/report.html 查看结果"

clean:
	rm -rf .pytest_cache reports/*.html reports/*.jsonl
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
