import requests
import shutil
import os
import urllib3
import ssl
from bs4 import BeautifulSoup
import argparse
import random

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

#Any item without a '.' is a directory, not a file
#If a directory contains no directories it is a root node
def is_root_node(items):
    return len([item for item in items if '.' not in item]) == 0

#List file should be the only .txt file in a directory
def get_list_file_name(items):
    return [item for item in items if '.txt' in item][0]

def recursive_traverse(url,path,single_directory_mode,n_images):
    print(n_images)
    items = get_directory_items(url)
    if(is_root_node(items)):
        #Directory contains images
        list_file_name = get_list_file_name(items)
        list_file = download_list_file(url,list_file_name,path,n_images=n_images)
        download_images(url,list_file,path)
        return
    
    #Directory contains directories
    #If in single directory mode, new directory is not created
    n_images_child = n_images/len(items) #Number of images needed from each child directory
    for item in items:
        if not single_directory_mode:
            new_directory_path = f"{path}/{item}"
            os.mkdir(new_directory_path)
        else:
            new_directory_path = path
        recursive_traverse(f"{url}/{item}",new_directory_path,single_directory_mode,n_images=n_images_child)



def download_images(base_url,list_file,base_path):
    with open(list_file) as f:
        image_names = f.read().split("\n")
    for name in image_names:
        url = f"{base_url}/{name}"
        file = f"{base_path}/{name}"
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

#Modify list file name to include offset and step
def modify_list_file_name(file_name,offset,step):
    #-8 index cuts out _all.txt
    return f"{file_name[:-8]}_offs_{offset}_step_{step}.txt"

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
                    print(f"{chance} / {len(data)}")
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

    try:
        recursive_traverse(args.base_url,args.file_path,args.single_directory_mode,args.number_images)
        print("Downloading completed")
    except DownloadCancelledException:
        pass
