PYTHON ?= python3

.PHONY: check test syntax install uninstall diagnose

check: test syntax

test:
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

syntax:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -c "from pathlib import Path; paths=list(Path('src').rglob('*.py')) + list(Path('tests').rglob('*.py')) + [Path('packaging/installer.py')]; [compile(path.read_text(encoding='utf-8'), str(path), 'exec') for path in paths]"

install:
	./install.sh

uninstall:
	./uninstall.sh

diagnose:
	PYTHONPATH=src $(PYTHON) -m dolphin_clean_title --diagnose
