summary.txt : currencies.json make_collection.py utils.py .wiki_cache/*
	./make_collection.py

currencies.json : read_currencies.py utils.py .wiki_cache/*
	./read_currencies.py
