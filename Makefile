summary.txt : make_collection.py currencies.json
	./make_collection.py

currencies.json : read_denoms.py .wiki_cache/* 
	./read_denoms.py
