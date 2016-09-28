.PHONY: build

PYTHON := python2.7

build:
	virtualenv -p ${PYTHON} env
	env/bin/pip install --upgrade --quiet pip wheel
	env/bin/pip install --quiet -r requirements.txt
	env/bin/python setup.py install
	pwd > env/lib/${PYTHON}/site-packages/perfrunner.pth

clean:
	rm -fr build perfrunner.egg-info dist
	find . -name '*.pyc' -o -name '*.pyo' | xargs rm -f

pep8:
	env/bin/flake8 --statistics cbagent perfdaily perfrunner scripts spring
	env/bin/isort --quiet --check-only --recursive cbagent perfdaily perfrunner scripts spring

nose:
	env/bin/nosetests -v unittests.py

test: nose pep8
