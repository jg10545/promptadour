import numpy as np
import panel as pn
import json
import matplotlib.pyplot as plt
from collections import defaultdict


def _initialize_ontology(whitelist={}, blacklist=[]):
    return {"blacklist":blacklist, "whitelist":whitelist}



def _get_tag_counts(taglist):
    """
    :taglist: list of lists
    """
    counter = defaultdict(int)
    for tags in taglist:
        for t in tags:
            counter[t] += 1
    return counter




def _build_widgets(alltags, tagtypes=["thing", "stuff", "context"]):
    widgets = {
    "currentkeyval":pn.pane.Markdown(object="##key:value"),
    "gridplot":pn.pane.Matplotlib(),
    "gridsamplebutton":pn.widgets.Button(name="Sample images"),
    "tagtype":pn.widgets.Select(options=tagtypes, value=tagtypes[0]),
    "strings":pn.widgets.TextInput(name="synonyms for tag", placeholder="enter comma-separated values"),
    "addtowhitelistbutton":pn.widgets.Button(name="Add key:value to whitelist", button_type="primary"),
    "addtoblacklistbutton":pn.widgets.Button(name="Add key:value to blacklist", button_type="warning"),
    "addkeytoblacklistbutton":pn.widgets.Button(name="Add key to blacklist", button_type="danger"),
    
    
    "nexttagbutton":pn.widgets.Button(name="Get most frequent unreviewed tag"),
    "randomtagbutton":pn.widgets.Button(name="Get random unreviewed tag"),
    "samekeybutton":pn.widgets.Button(name="Get random tag with same key"),
    "taginput":pn.widgets.AutocompleteInput(name="Choose tag to review", options=alltags,
                                           placeholder="type key:value pair"),
    "gettagbutton":pn.widgets.Button(name="Retrieve tag"),
    "nonzero_indicator":pn.indicators.Progress(name='Fraction of images with at least one tag', value=0, max=100),
    "reviewed_indicator":pn.indicators.Progress(name='Fraction of tags reviewed', value=0, max=100)
    }
    
    selectcol = ["nexttagbutton", "randomtagbutton", "samekeybutton", "taginput", "gettagbutton"]
    savecol = ["currentkeyval", "tagtype", "strings", "addtowhitelistbutton", 
           "addtoblacklistbutton", "addkeytoblacklistbutton"]
    imcol = ["gridplot", "gridsamplebutton", "nonzero_indicator", "reviewed_indicator"]
    
    selectcol = pn.Column(*[widgets[b] for b in selectcol], align="end")
    savecol = pn.Column(*[widgets[b] for b in savecol], align="end")
    imcol = pn.Column(*[widgets[b] for b in imcol], align="end")
    layout = pn.Row(selectcol, savecol, imcol)
    
    return widgets, layout


def _gridplot(imfiles):
    fig, axs = plt.subplots(nrows=3, ncols=3)
    for i in range(3):
        for j in range(3):
            k = i*3 + j
            if k < len(imfiles):
                axs[i,j].imshow(Image.open(imfiles[k]))
            axs[i,j].set_axis_off()
    return fig


class OntFarm():
    """
    Object to try and streamline the process of organizing messy key:value pairs
    into a format we can use for random prompt generation
    """
    def __init__(self, taglist, filepaths=None, tagtypes=["thing", "stuff", "context"], 
                 ontology=None, whitelist={},
                 blacklist=[], load_from=None,
                min_counts=1, saveto=None):
        """
        :taglist: list of lists containing tags for each image
        :filepaths: list of locations for each image
        :tagtypes: allowed types of tags for your ontology
        :ontology: pre-built ontology to start from
        :whitelist: pre-built whitelist to start from
        :blacklist: pre-built blacklist to start from
        :load_from: file containing pre-build ontology to start from
        """
        if ontology is None:
            ontology = _initialize_ontology(whitelist, blacklist)
        self.ontology = ontology
        if load_from is not None:
            self._load_ontology(load_from)
            
        self.saveto = saveto
            
        # get a count of how many times each tag appears
        self.tag_counts = _get_tag_counts(taglist)
        # also see which tags have not yet reviewed
        self.unreviewed_tag_counts = {k:self.tag_counts[k] for k in self.tag_counts if 
                                      not (self._is_blacklisted(k)|self._is_whitelisted(k))}
        self.filepaths = filepaths
        self.taglist = taglist
        self.tagtypes = tagtypes
        
        self._prune_unreviewed_list(min_counts=min_counts)
        self._widgets, self._layout = _build_widgets(list(self.tag_counts.keys()), tagtypes)
        self._configure_buttons()
        
        
    def _configure_buttons(self):
        w = self._widgets
        w["nexttagbutton"].on_click(self._most_frequent_button_callback)
        w["randomtagbutton"].on_click(self._random_button_callback)
        w["samekeybutton"].on_click(self._same_key_button_callback)
        w["addtowhitelistbutton"].on_click(self._add_to_whitelist_callback)
        w["addtoblacklistbutton"].on_click(self._add_to_blacklist_callback)
        w["addkeytoblacklistbutton"].on_click(self._add_key_to_blacklist_callback)
        w["gridsamplebutton"].on_click(self._gui_sample_images)
        w["gettagbutton"].on_click(self._load_button_callback)
    
    def _gui_update_indicators(self):
        tagstats = self._compute_tag_statistics()
        self._widgets["nonzero_indicator"].value = int(100*tagstats["frac_at_least_one"])
        self._widgets["reviewed_indicator"].value = int(100*tagstats["reviewed_frac"])
    
    def _gui_sample_images(self, *events):
        if hasattr(self, "_current_tag_images"):
            sample = np.random.choice(self._current_tag_images, size=min(9, len(self._current_tag_images)),
                                     replace=False)
            self._widgets["gridplot"].object = _gridplot(sample)
    
    def _gui_load_tag(self, tag):
        # load the tag
        self._widgets["currentkeyval"].object = f"##{tag}"
        self._widgets["strings"].value = tag
        self._current_tag = tag
        self._current_tag_images = [f for f,t in zip(self.filepaths, self.taglist)
                                   if tag in t]
        # if the tag is already in the whitelist, update widgets accordingly
        if tag in self.ontology["whitelist"]:
            self._widgets["tagtype"].value = self.ontology["whitelist"][tag]["tagtype"]
            self._widgets["strings"].value = ",".join(self.ontology["whitelist"][tag]["strings"])
            
        # update plot
        self._gui_sample_images()
        
    def _most_frequent_button_callback(self, *events):
        tag = self.find_most_frequent_unreviewed_tag()
        self._gui_load_tag(tag)
        
    def _random_button_callback(self, *events):
        tag = self.sample_unreviewed_tags()
        self._gui_load_tag(tag)
        
    def _same_key_button_callback(self, *events):
        newtag = self.sample_unreviewed_tag_with_same_key(self._current_tag)
        self._gui_load_tag(newtag)
        
    def _load_button_callback(self, *events):
        tag = self._widgets["taginput"].value
        self._gui_load_tag(tag)
        
    def _add_to_whitelist_callback(self, *events):
        tagtype = self._widgets["tagtype"].value
        strings = [x.strip() for x in self._widgets["strings"].value.split(",")]
        self.add_to_whitelist(self._current_tag, strings, tagtype)
        self._gui_update_indicators()
        
    def _add_to_blacklist_callback(self, *events):
        self.add_to_blacklist(self._current_tag)
        self._gui_update_indicators()
        
    def _add_key_to_blacklist_callback(self, *events):
        self.add_to_blacklist(self._current_tag.split(":")[0])
        self._gui_update_indicators()
        self.save()
    
    def add_to_blacklist(self, tag):
        """
        Add a key or key:value pair to blacklist
        """
        if tag in self.ontology["blacklist"]:
            logging.warn(f"tag {tag} already in blacklist")
        elif tag.split(":")[0] in self.ontology["blacklist"]:
            logging.warn(f"key from tag {tag} already in blacklist")
        else:
            self.ontology["blacklist"].append(tag)
            logging.info(f"adding {tag} to blacklist")
        if self._is_whitelisted(tag):
            self.ontology["whitelist"].__delitem__(tag)
            logging.info(f"removing {tag} from whitelist since it's blacklisted now")
        self._remove_from_unreviewed_list(tag)
        self.save()
        
    def add_to_whitelist(self, tag, strings, tagtype="thing"):
        """
        Add a tag to the whitelist
        """
        self.ontology["whitelist"][tag] = {"tagtype":tagtype, "strings":strings}
        stringstring = ','.join(strings)
        logging.info(f"adding {tag} to whitelist with type {tagtype} and strings [{stringstring}]")
        self._remove_from_unreviewed_list(tag)
        self.save()
        
    
    def save(self, filepath=None):
        """
        save to a JSON or YAML
        """
        if filepath is None:
            filepath = self.saveto
        if filepath is not None:
            json.dump(self.ontology, open(filepath, "w"))
    
    def _load_ontology(self, filepath):
        """
        load a JSON ontology
        """
        if filepath.lower().endswith("json"):
            self.ontology = json.load(open(filepath, "r"))
        else:
            assert False, "not yet implemented"
    
    def _is_blacklisted(self, tag):
        """
        Am I in the blacklist?
        
        :tag: string containing a "key:value" pair
        """
        blacklist = self.ontology["blacklist"]
        return (tag in blacklist)|(tag.split(":")[0] in blacklist)
        
    def _is_whitelisted(self, tag):
        """
        Am I in the whitelist already?
        """
        return tag in self.ontology["whitelist"]
    
    def find_most_frequent_unreviewed_tag(self):
        highest_index = np.argmax(list(self.unreviewed_tag_counts.values()))
        tag = list(self.unreviewed_tag_counts.keys())[highest_index]
        logging.info(f"recommending most frequent unreviewed tag: {tag}")
        return tag
    
    def sample_unreviewed_tags(self):
        tagcounts = np.array(list(self.unreviewed_tag_counts.values()))
        tag = np.random.choice(list(self.unreviewed_tag_counts.keys()), 
                               p=tagcounts/tagcounts.sum())
        logging.info(f"recommending random unreviewed tag: {tag}")
        return tag
    
    def sample_unreviewed_tag_with_same_key(self, tag):
        key = tag.split(":")[0]
        tags_with_same_key = [t for t in self.unreviewed_tag_counts if (t.split(":")[0]==key)&(t != tag)]
        if len(tags_with_same_key) > 0:
            newtag = np.random.choice(tags_with_same_key)
            logging.info(f"recommending new tag with same key as {tag}: {newtag}")
            return newtag
        else:
            return tag
    
    def _remove_from_unreviewed_list(self, tag):
        # if it's a key:value pair, remove that pair from the dictionary
        if (":" in tag)&(tag in self.unreviewed_tag_counts):
            self.unreviewed_tag_counts.__delitem__(tag)
            logging.info(f"removing {tag} from unreviewed list")
        # if it's just a key- remove any key:value pair containing that key
        elif ":" not in tag:
            counter = 0
            for k in list(self.unreviewed_tag_counts.keys()):
                if k.split(":")[0] == tag:
                    self.unreviewed_tag_counts.__delitem__(k)
                    counter += 1
            if counter > 0:
                logging.info(f"removed {counter} tags from unreviewed list matching tag {tag}")
                    
    def _prune_unreviewed_list(self, blacklist=True, whitelist=True, min_counts=1):
        logging.info("pruning unreviewed list")
        if whitelist:
            for tag in self.ontology["whitelist"]:
                self._remove_from_unreviewed_list(tag)
        if blacklist:
            for tag in self.ontology["blacklist"]:
                self._remove_from_unreviewed_list(tag)
        if min_counts > 1:
            for tag in list(self.unreviewed_tag_counts.keys()):
                if self.unreviewed_tag_counts[tag] < min_counts:
                    self._remove_from_unreviewed_list(tag)
                    
    def _compute_tag_statistics(self):
        reviewed_frac = 1 - len(self.unreviewed_tag_counts)/len(self.tag_counts)
        whitelisted_tag_count = np.array([len([t for t in tags if t in self.ontology["whitelist"]])
                                         for tags in self.taglist])
        frac_at_least_one = np.mean(whitelisted_tag_count > 0)
        return {"reviewed_frac":reviewed_frac, "frac_at_least_one":frac_at_least_one}
    
    def serve(self, **kwargs):
        """
        wrapper for panel.serve()
        """
        p = self._layout
        pn.serve(p, title="here's a GUI. are you happy now?", **kwargs)