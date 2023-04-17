import requests
import shutil
import os
import urllib3
import ssl
from bs4 import BeautifulSoup
import argparse
import random
import math

class DownloadCancelledException(Exception):
    pass


#Needed to get around SSL issue
class CustomHttpAdapter (requests.adapters.HTTPAdapter):
    # "Transport adapter" that allows us to use custom ssl_context.

    def __init__(self, ssl_context=None, **kwargs):
        self.ssl_context = ssl_context
        super().__init__(**kwargs)

    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = urllib3.poolmanager.PoolManager(
            num_pools=connections, maxsize=maxsize,
            block=block, ssl_context=self.ssl_context)


def get_legacy_session():
    ctx = ssl._create_unverified_context()
    ctx.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
    session = requests.session()
    session.mount('https://', CustomHttpAdapter(ctx))
    return session


def get_directory_items(url):
    page = get_legacy_session().get(url,verify=False).text
    soup = BeautifulSoup(page,'html.parser')
    #Remove parent directory and column sorting buttons
    return [node.get('href') for node in soup.find_all('a') if '?' not in node.get('href') and node.string != "Parent Directory"]

def count_root_directories(url):
    items = get_directory_items(url)
    if(is_root_node(items)):
        return 1
    return sum([count_root_directories(f"{url}/{item}") for item in items])

#Any item without a '.' is a directory, not a file
#If a directory contains no directories it is a root node
def is_root_node(items):
    return len([item for item in items if '.' not in item]) == 0

#List file should be the only .txt file in a directory
def get_list_file_name(items):
    text_files = [item for item in items if '.txt' in item]
    #Avoid location files
    return text_files[0] if len(text_files)>0 and not "_loc" in text_files[0] else None

def recursive_traverse(url,path,single_directory_mode,n_images,relative_name=""):
    items = get_directory_items(url)
    if(is_root_node(items)):
        #Directory contains images
        list_file_name = get_list_file_name(items)
        if list_file_name != None:
            list_file = download_list_file(url,list_file_name,path,n_images=n_images)
        else:
            list_file = create_list_file(items,path,n_images,relative_name)
        if list_file:
            download_images(url,list_file,path,relative_name)
        return
    
    #Directory contains directories
    #If in single directory mode, new directory is not created
    for item in items:
        child_relative_name = relative_name
        if not single_directory_mode:
            new_directory_path = f"{path}/{item}"
            os.mkdir(new_directory_path)
        else:
            new_directory_path = path
            #Remove slashes
            child_relative_name = (relative_name + item[:-1])
        recursive_traverse(f"{url}/{item}",new_directory_path,single_directory_mode,n_images=n_images,relative_name=child_relative_name)



def download_images(base_url,list_file,base_path,relative_name=""):
    with open(list_file) as f:
        image_names = f.read().split("\n")
    for name in image_names:
        url = f"{base_url}/{name}"
        file = f"{base_path}/{relative_name}_{name}"
        #Check file already exists
        if not os.path.exists(file):
            print(f"Downloading: {url}")
            try:
                res = get_legacy_session().get(url,stream = True,verify=False)
                if res.status_code == 200:
                    with open(file,'wb') as f:
                        shutil.copyfileobj(res.raw,f)
            except KeyboardInterrupt:
                print(f"Cancelled downloading:{url}, deleting created file")
                os.remove(file)
                raise DownloadCancelledException
            print(f"Finished downloading: {url}")
    print(f"All files in {url} downloaded")

def create_list_file(items,base_path,n_images,relative_name):
    file = f"{base_path}/{relative_name}.txt"
    if not os.path.exists(file):
        image_files = [item for item in items if ".JPG" in item]
        #Chance of each image being selected such that it is likely that n images are selected from this directory
        chance = n_images/len(image_files)
        randoms = [random.random() for i in range(len(image_files))]
        data = "\n".join([file for file,p in zip(image_files,randoms) if p < chance])
        #If no images are included in the file, do not create it
        if len(data) == 0:
            return None
        with open(file,'w') as f:
            f.write(data)
    return file

def download_list_file(base_url,list_file,base_path,n_images):
    url = f"{base_url}/{list_file}"
    file = f"{base_path}/{list_file}"
    #Check file already exists
    if not os.path.exists(file):
        print(f"Downloading: {url}")
        try:
            res = get_legacy_session().get(url,verify=False)
            if res.status_code == 200:
                #Apply step and offset to list file
                data = res._content.decode("utf-8")
                if n_images!=None:
                    data = data.split("\n")
                    #Chance of each image being selected such that it is likely that n images are selected from this directory
                    chance = n_images/len(data)
                    randoms = [random.random() for i in range(len(data))]
                    data = "\n".join([file for file,p in zip(data,randoms) if p < chance])
                with open(file,'w') as f:
                    f.write(data)
        except KeyboardInterrupt:
            print(f"Cancelled downloading:{url}, deleting created file")
            os.remove(file)
            raise DownloadCancelledException
        print(f"Finished downloading: {url}")
    return file

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('base_url')
    parser.add_argument('-f','--file_path',default=".")
    parser.add_argument('-s',"--single_directory_mode",action='store_true')
    parser.add_argument('-n','--number_images',default=None,type=int)
    args = parser.parse_args()

    n_root_dirs = count_root_directories(args.base_url)
    images_per_dir = math.ceil(args.number_images/n_root_dirs)

    try:
        recursive_traverse(args.base_url,args.file_path,args.single_directory_mode,images_per_dir)
        print("Downloading completed")
    except DownloadCancelledException:
        pass
