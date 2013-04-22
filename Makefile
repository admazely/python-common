.PHONY: test

test-fast:
	-nosetests --exe .

test:
	-nosetests --exe --attr=slow

cover:
	-nosetests --with-coverage --cover-inclusive --exe --attr=slow
	
lint:
	-find . -iname '*.py' | sort | xargs pylint -i y -r n -d C,R,I,W0142,E1103,W0603,W0613,W0141 -f colorized

clean:
	-find . -iname '*.pyc' -delete
	
all: clean cover lint

