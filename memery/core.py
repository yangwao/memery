# AUTOGENERATED! DO NOT EDIT! File to edit: 03_fileutils.ipynb (unless otherwise specified).

__all__ = ['MemeFolder', 'printi', 'top_bottom', 'copy_topn_images']

# Cell
import torch
import torchvision
import clip

from pathlib import Path
from annoy import AnnoyIndex

from IPython.display import Image, display
from tqdm import tqdm

# Cell
class MemeFolder:
    """Takes an image folder and a CLIP model and calculates the encodings for each image"""

    def __init__(self, folder_str, clip_model="ViT-B/32", clear_cache=False, use_treemap=True):
        self.clear_cache = clear_cache
        self.path = Path(folder_str)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model, self.preprocess = clip.load(clip_model, device=self.device)
        self.logit_scale = self.model.logit_scale.exp()

        if use_treemap == True:
            self.names = self.images_to_treemap(self.preprocess)
        else:
            self.names, self.features = self.images_to_dict()

    def __str__(self):
        return(f'MemeFolder from {str(self.path)}, {len(self.names)} images')

    def __repr__(self): return(self.__str__())

    def __len__(self): return(len(self.names))

    def preproc_images(self):
        '''Batch process images with CLIP and return their feature embeddings'''
        image_features = torch.tensor(()).to(self.device)
        with torch.no_grad():
            imagefiles=torchvision.datasets.ImageFolder(root=self.path, transform=self.preprocess)
            img_loader=torch.utils.data.DataLoader(imagefiles, batch_size=128, shuffle=False, num_workers=4)
            for images, labels in tqdm(img_loader):
                batch_features = self.model.encode_image(images)
                image_features = torch.cat((image_features, batch_features)).to(self.device)

        image_names = [Path(f[0]) for f in imagefiles.imgs]
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)

        return(image_names, image_features)

    def images_to_dict(self):
        """Calculate image encodings from folder.
        TODO: Fix recursive loading to include self folder
        """
        savefile = self.path/'memery.pt'
        if self.clear_cache == True and savefile.exists():
            savefile.unlink() # remove savefile if need be
        # load or generate the encodings 🗜️
        # currently this just checks to see if there's a savefile, not if anything has changed since save time
        if savefile.exists():
            save_dict = torch.load(savefile)
            image_names = [k for k in save_dict.keys()]
            image_features = torch.stack([v for v in save_dict.values()]).to(self.device)
        else:
            image_names, image_features = self.preproc_images()
            save_dict = {str(k):v for k, v in zip(image_names, image_features)}
            torch.save(save_dict, savefile)
        return(image_names, image_features)

    def images_to_treemap(self, preprocess, clear_cache=False):
        """Calculate image encodings from folder and encode to treeman
        TODO: Fix recursive loading to include self folder, incorporate with images_to_dict better
        """
        self.treemap = AnnoyIndex(512, 'angular')
        savefile = self.path/'memery.ann'
        namefile = self.path/'names.txt'

        if clear_cache == True and savefile.exists():
            savefile.unlink()

        if savefile.exists():
            self.treemap.load(str(savefile))
            with open(str(namefile), 'r') as f:
                image_names =  [Path(o[:-1]) for o in f.readlines()]
        else:
            image_names, image_features = self.preproc_images()
            print("building trees...")
            for i, img in enumerate(image_features):
                self.treemap.add_item(i, img)

            # Build the treemap, with 10 trees rn
            self.treemap.build(10)

            # Save annoy index and list of filenames
            self.treemap.save(str(savefile))
            with open(str(namefile), 'w') as f:
                f.writelines([f'{str(o)}\n' for o in image_names])
        return(image_names)

    def predict_from_text_dict(self, query):
        """CLIPify the text query and compare to each image. Returns a sorted dictionary of names
        and scores
        """
        with torch.no_grad():
            text = clip.tokenize(query).to(self.device)
            text_features = self.model.encode_text(text)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)

            # matrix-vector product as logits
            logits_per_image = self.logit_scale * self.features @ text_features.float().t()

        scores = {self.names[i]: logit for i, logit in enumerate(logits_per_image)}
        top_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        return([str(file) for file, score in top_scores])

    def predict_from_text_trees(self, query):
        """CLIPify the text query and find nearest neighbors using treemap"""
        with torch.no_grad():
            text = clip.tokenize(query).to(self.device)
            text_features = self.model.encode_text(text)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)

        nn_indexes = self.treemap.get_nns_by_vector(text_features.t(), self.treemap.get_n_items())
        return([str(self.names[i]) for i in nn_indexes])

#     def predict_from_image_trees(self, query_img):
#         """UNTESTED: CLIPify an image and find nearest neighbors using treemap. doesn't work yet"""
#         with torch.no_grad():
#             image = clip.tokenize(query_images).to(device)
#             image_features = model.encode_image(image)
#             image_features = image_features / image_features.norm(dim=-1, keepdim=True)

#         nn_indexes = t.get_nns_by_vector(image_features.t(), self.treemap.get_n_items())
#         return(nn_indexes)

# Cell
def printi(images, n = 3, w = 200, start_index = 0):
    for im in images[start_index:start_index + n]:
#         print(f'{im}')
        try:
            display(Image(filename=im, width=w))
        except Exception as e:
            print(e)
# printi(image_names, 1)

# Cell
def top_bottom(query):
    results = predict_from_text(image_names, image_features, query)
    inv_results = sorted(results, key=lambda o: o[1])
    print(query.upper())
    n = 10
    w = 200
    print(f'top {n}')
    printi([file for file, score in results], n, w)
    print(f'bottom {n}')
    printi([file for file, score in inv_results], n, w)

# Cell
def copy_topn_images(results, outpath, n):
    for file, score in results[:n]:
        prefix = str(int(10*float(score)))
        filepath = Path(file)
        filename = '-'.join(filepath.parts[-2:])
        outfile = outpath/f'{prefix}-{filename}'
        outfile.write_bytes(filepath.read_bytes())