PYTHON := $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; else echo python3; fi)

.PHONY: setup doctor skills test demo qa studio clean

setup:
	./setup.sh

doctor:
	./sf doctor

skills:
	./sf skills index
	./sf skills list

test:
	$(PYTHON) -m unittest discover -s tests -v
	$(PYTHON) -m compileall -q shortsforge

demo:
	./sf render examples/demo_3_erreurs.yaml --qa

qa:
	./sf qa examples/demo_3_erreurs.yaml

studio:
	./sf studio --host 0.0.0.0 --port 8080

clean:
	rm -rf output/.work output/.thumbs
