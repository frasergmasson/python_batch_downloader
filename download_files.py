import requests
import shutil
import sys
import os
import urllib3
import ssl
from bs4 import BeautifulSoup
import getopt
import argparse

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

def recursive_traverse(url,path,single_directory_mode,offset,step):
    items = get_directory_items(url)
    if(is_root_node(items)):
        #Directory contains images
        list_file_name = get_list_file_name(items)
        list_file = download_list_file(url,list_file_name,path,offset=offset,step=step)
        download_images(url,list_file,path)
        return
    
    #Directory contains directories
    #If in single directory mode, new directory is not created
    for item in items:
        if not single_directory_mode:
            new_directory_path = f"{path}/{item}"
            os.mkdir(new_directory_path)
        else:
            new_directory_path = path
        recursive_traverse(f"{url}/{item}",new_directory_path,single_directory_mode,offset=offset,step=step)



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

def download_list_file(base_url,list_file,base_path,offset=0,step=0):
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
                if offset !=0 or step!=0:
                    data = data.split("\n")
                    data = "\n".join([data[i] for i in range(offset,len(data),step)])
                    file = modify_list_file_name(file,offset,step)
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
    parser.add_argument('--step',type=int)
    parser.add_argument('--offset',type=int)
    args = parser.parse_args()

    try:
        recursive_traverse(args.base_url,args.file_path,args.single_directory_mode,args.offset,args.step)
        print("Downloading completed")
    except DownloadCancelledException:
        pass
