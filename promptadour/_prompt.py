import numpy as np

DEFAULT_ARTICLES = {"thing":["a", "an", "the"],
           "stuff":["near","by","in", ""],
           "context":["in"]}
DEFAULT_TAGTYPES = ["thing", "stuff", "context"]

def prompterate(tags, ont, max_per_type=2, articles=DEFAULT_ARTICLES, tagtypes=DEFAULT_TAGTYPES):
    """
    
    """
    # for each tag, check if it's in the whitelist and pick one of the 
    # string representations if it is
    strings_and_types = [(np.random.choice(ont["whitelist"][t]["strings"]), 
                          ont["whitelist"][t]["tagtype"])
                         for t in tags if t in ont["whitelist"]]
    
    prompt = []
    for tagtype in tagtypes:
        strings = [t[0] for t in strings_and_types if t[1] == tagtype]
        if len(strings) > 0:
            strings = np.random.choice(strings, size=min(len(strings), max_per_type), replace=False)
            for e,s in enumerate(strings):
                if e > 0:
                    prompt.append("and")
                prompt.append(np.random.choice(articles[tagtype]))
                prompt.append(s)

    prompt = " ".join(prompt)
    return prompt.replace("  ", " ")