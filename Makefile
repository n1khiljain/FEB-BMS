PY := python3

.PHONY: run test clean

run:
	$(PY) sim.py

test:
	$(PY) -m unittest discover -s tests -t . -v

clean:
	rm -rf __pycache__ */__pycache__ .pytest_cache
