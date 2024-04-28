format-black:
	@black ./src
format-isort:
	@isort ./src
lint-black:
	@black ./src --check
lint-isort:
	@isort ./src -- check
lint-flake8:
	@flake8 ./src

lint: lint-black lint-isort lint-flake8
format: format-black format-isort
