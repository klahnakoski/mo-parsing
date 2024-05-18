## Contributing

After forking the mo-parsing repo, and cloning your fork locally, install the libraries needed to run tests

If you are interested in enhancing or extending this code: First verify the code passes tests 
     
For __Linux__:

	git clone https://github.com/klahnakoski/mo-parsing.git
	cd mo-parsing
	pip install -r tests/requirements.txt
	pip install -r requirements.txt
	export PYTHONPATH=.	
	python -m unittest discover tests

For __Windows__:

	git clone https://github.com/klahnakoski/mo-parsing.git
	cd mo-parsing
	c:\Python311\python.exe -m pip install -r tests\requirements.txt
	c:\Python311\python.exe -m pip install -r requirements.txt
	set PYTHONPATH=.	
	c:\Python311\python.exe -m -m unittest discover tests


