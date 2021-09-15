## Contributing

After forking the mo-parsing repo, and cloning your fork locally, install the libraries needed to run tests

If you are interested in enhancing or extending this code: First verify the code passes tests 
     
For __Linux__:

	git clone https://github.com/klahnakoski/mo-parsing.git
	cd mo-parsing
	pip install -r requirements.txt
	pip install -r tests/requirements.txt
	export PYTHONPATH=.	
	python -m unittest discover tests

For __Windows__:

	git clone https://github.com/klahnakoski/mo-parsing.git
	cd mo-parsing
	pip install -r requirements.txt
	pip install -r tests\requirements.txt
	set PYTHONPATH=.	
	python.exe -m unittest discover tests


