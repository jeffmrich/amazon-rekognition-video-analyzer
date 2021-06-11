"""Prepare MS COCO datasets for custom Rekognition training"""
import os
import argparse
import zipfile
import json
import random
import shutil
import datetime
import botocore
import boto3
import io
import PIL.Image as image
from pathlib import Path
from gluoncv.utils import download, makedirs


class CocoFilter():
    """ Filters the COCO dataset
    """
    def _process_info(self):
        self.info = self.coco['info']
        
    def _process_licenses(self):
        self.licenses = self.coco['licenses']
        
    def _process_categories(self):
        self.categories = dict()
        self.super_categories = dict()
        self.category_set = set()

        for category in self.coco['categories']:
            cat_id = category['id']
            super_category = category['supercategory']
            
            # Add category to categories dict
            if cat_id not in self.categories:
                self.categories[cat_id] = category
                self.category_set.add(category['name'])
            else:
                print(f'ERROR: Skipping duplicate category id: {category}')
            
            # Add category id to the super_categories dict
            if super_category not in self.super_categories:
                self.super_categories[super_category] = {cat_id}
            else:
                self.super_categories[super_category] |= {cat_id} # e.g. {1, 2, 3} |= {4} => {1, 2, 3, 4}

    def _process_images(self):
        self.images = dict()
        for image in self.coco['images']:
            image_id = image['id']
            if image_id not in self.images:
                self.images[image_id] = image
            else:
                print(f'ERROR: Skipping duplicate image id: {image}')
                
    def _process_segmentations(self):
        self.segmentations = dict()
        for segmentation in self.coco['annotations']:
            image_id = segmentation['image_id']
            if image_id not in self.segmentations:
                self.segmentations[image_id] = []
            self.segmentations[image_id].append(segmentation)

    def _filter_categories(self):
        """ Find category ids matching args
            Create mapping from original category id to new category id
            Create new collection of categories
        """
        missing_categories = set(self.filter_categories) - self.category_set
        if len(missing_categories) > 0:
            print(f'Did not find categories: {missing_categories}')
            should_continue = input('Continue? (y/n) ').lower()
            if should_continue != 'y' and should_continue != 'yes':
                print('Quitting early.')
                quit()

        self.new_category_map = dict()
        new_id = 1
        for key, item in self.categories.items():
            if item['name'] in self.filter_categories:
                self.new_category_map[key] = new_id
                new_id += 1

        self.new_categories = []
        for original_cat_id, new_id in self.new_category_map.items():
            new_category = dict(self.categories[original_cat_id])
            new_category['id'] = new_id
            self.new_categories.append(new_category)

    def _filter_annotations(self):
        """ Create new collection of annotations matching category ids
            Keep track of image ids matching annotations
        """
        self.new_segmentations = []
        self.new_image_ids = set()
        for image_id, segmentation_list in self.segmentations.items():
            for segmentation in segmentation_list:
                original_seg_cat = segmentation['category_id']
                if original_seg_cat in self.new_category_map.keys():
                    new_segmentation = dict(segmentation)
                    new_segmentation['category_id'] = self.new_category_map[original_seg_cat]
                    self.new_segmentations.append(new_segmentation)
                    self.new_image_ids.add(image_id)

    def _filter_images(self):
        """ Create new collection of images
        """
        self.new_images = []
        for image_id in self.new_image_ids:
            self.new_images.append(self.images[image_id])

    def main(self, args, input_json, output_json):
        # Open json
        # self.input_json_path = Path(args.input_json)
        self.input_json_path = Path(input_json)
        # self.output_json_path = Path(args.output_json)
        self.output_json_path = Path(output_json)
        self.filter_categories = args.categories

        # Verify input path exists
        if not self.input_json_path.exists():
            print('Input json path not found.')
            print('Quitting early.')
            quit()

        # Verify output path does not already exist
        if self.output_json_path.exists():
            should_continue = input('Output path already exists. Overwrite? (y/n) ').lower()
            if should_continue != 'y' and should_continue != 'yes':
                print('Quitting early.')
                quit()
        
        # Load the json
        print('Loading json file...')
        with open(self.input_json_path) as json_file:
            self.coco = json.load(json_file)
        
        # Process the json
        print('Processing input json...')
        self._process_info()
        self._process_licenses()
        self._process_categories()
        self._process_images()
        self._process_segmentations()

        # Filter to specific categories
        print('Filtering...')
        self._filter_categories()
        self._filter_annotations()
        self._filter_images()

        # Build new JSON
        new_master_json = {
            'info': self.info,
            'licenses': self.licenses,
            'images': self.new_images,
            'annotations': self.new_segmentations,
            'categories': self.new_categories
        }

        # Write the JSON to a file
        print('Saving new json file...')
        with open(self.output_json_path, 'w+') as output_file:
            json.dump(new_master_json, output_file)

        print('Filtered json saved.')


# class representing a Custom Label JSON line for an image
class cl_json_line:  
    def __init__(self,job, img):  

        #Get image info. Annotations are dealt with seperately
        sizes=[]
        image_size={}
        image_size["width"] = img["width"]
        image_size["depth"] = 3
        image_size["height"] = img["height"]
        sizes.append(image_size)

        bounding_box={}
        bounding_box["annotations"] = []
        bounding_box["image_size"] = sizes

        self.__dict__["source-ref"] = s3_path + img['file_name']
        self.__dict__[job] = bounding_box

        #get metadata
        metadata = {}
        metadata['job-name'] = job_name
        metadata['class-map'] = {}
        metadata['human-annotated']='yes'
        metadata['objects'] = [] 
        date_time_obj = datetime.datetime.strptime(img['date_captured'], '%Y-%m-%d %H:%M:%S')
        metadata['creation-date']= date_time_obj.strftime('%Y-%m-%dT%H:%M:%S') 
        metadata['type']='groundtruth/object-detection'
        
        self.__dict__[job + '-metadata'] = metadata


def parse_args():
    parser = argparse.ArgumentParser(
        description='Initialize MS COCO dataset.',
        epilog='Example: python mscoco.py --download-dir ~/mscoco',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--download-dir', type=str, default='~/mscoco/', help='dataset directory on disk')
    parser.add_argument('--no-download', action='store_true', help='disable automatic download if set')
    parser.add_argument('--overwrite', action='store_true', help='overwrite downloaded files if set, in case they are corrupted')
    # parser.add_argument('--input_json', dest="input_json", help="path to a json file in coco format")
    # parser.add_argument('--output_json', dest="output_json", help="path to save the output json")
    # parser.add_argument('--categories', nargs='+', dest="categories", help="List of category names separated by spaces, e.g. --categories dog ")
    parser.add_argument('--categories', nargs='+', dest="categories", help="List of category names separated by spaces, e.g. --categories boat ")
    parser.add_argument('--bucket', dest='bucket', type=str, required=True, help='S3 bucket name for Rekognition')
    args = parser.parse_args()
    return args


def download_coco(path, overwrite=False):
    _DOWNLOAD_URLS = [
        ('http://images.cocodataset.org/zips/train2017.zip',
         '10ad623668ab00c62c096f0ed636d6aff41faca5'),
        ('http://images.cocodataset.org/annotations/annotations_trainval2017.zip',
         '8551ee4bb5860311e79dace7e79cb91e432e78b3'),
        # ('http://images.cocodataset.org/zips/val2017.zip',
        #  '4950dc9d00dbe1c933ee0170f5797584351d2a41')
    ]
    makedirs(path)
    for url, checksum in _DOWNLOAD_URLS:
        filename = download(url, path=path, overwrite=overwrite, sha1_hash=checksum)
        # extract
        with zipfile.ZipFile(filename) as zf:
            zf.extractall(path=path)
        os.remove(filename)

if __name__ == '__main__':
    args = parse_args()
    path = os.path.expanduser(args.download_dir)
    if not os.path.isdir(path) or not os.path.isdir(os.path.join(path, 'train2017')) \
        or not os.path.isdir(os.path.join(path, 'val2017')) \
        or not os.path.isdir(os.path.join(path, 'annotations')):
        if args.no_download:
            pass
        else:
            download_coco(path, overwrite=args.overwrite)

    print(f'Creating custom category: {"".join(args.categories)}')
    input_json = os.path.join(path, 'annotations', 'instances_train2017.json')
    output_json = os.path.join(path, 'annotations', f'{"".join(args.categories)}.json')
    cf = CocoFilter()
    cf.main(args, input_json, output_json)

    print(f'Transforming COCO {"".join(args.categories)} into Rekognition Custom manifest file')
    s3_bucket = args.bucket
    s3_key_path_manifest_file = f'{"".join(args.categories)}/manifest/'
    s3_key_path_images = f'{"".join(args.categories)}/images/'
    s3_path='s3://' + s3_bucket  + '/' + s3_key_path_images
    s3 = boto3.resource('s3')
    local_path = path+'/'
    local_images_path = os.path.join(path, 'train2017')
    coco_manifest = os.path.join('annotations', f'{"".join(args.categories)}.json')
    coco_json_file = local_path + coco_manifest
    job_name = f'Custom Labels job name for {"".join(args.categories)}'
    cl_manifest_file = 'custom_labels.manifest'
    label_attribute ='bounding-box'
    open(local_path + cl_manifest_file, 'w').close()

    print("Getting image, annotations, and categories from COCO file...")
    with open(coco_json_file) as f:
        js = json.load(f)
        images = js['images']
        categories = js['categories']
        annotations = js['annotations']

    print('Images: ' + str(len(images)))
    print('annotations: ' + str(len(annotations)))
    print('categories: ' + str(len (categories)))

    print("Creating CL JSON lines...")
    images_dict = {image['id']: cl_json_line(label_attribute, image) for image in images}
    print('Parsing annotations...')
    for annotation in annotations:
        image=images_dict[annotation['image_id']]
        cl_annotation = {}
        cl_class_map={}
        cl_bounding_box={}
        cl_bounding_box['left'] = annotation['bbox'][0]
        cl_bounding_box['top'] = annotation['bbox'][1]
        cl_bounding_box['width'] = annotation['bbox'][2]
        cl_bounding_box['height'] = annotation['bbox'][3]
        cl_bounding_box['class_id'] = annotation['category_id']
        getattr(image, label_attribute)['annotations'].append(cl_bounding_box)

        for category in categories:
            if annotation['category_id'] == category['id']:
                getattr(image, label_attribute + '-metadata')['class-map'][category['id']]=category['name']
        
        cl_object={}
        cl_object['confidence'] = int(1)
        getattr(image, label_attribute + '-metadata')['objects'].append(cl_object)
        
    print('Done parsing annotations')
    print('Writing Custom Labels manifest...')
    for im in images_dict.values():
        with open(local_path+cl_manifest_file, 'a+') as outfile:
            json.dump(im.__dict__,outfile)
            outfile.write('\n')
            outfile.close()
    
    print ('Uploading Custom Labels manifest file to S3 bucket')
    print('Uploading'  + local_path + cl_manifest_file + ' to ' + s3_key_path_manifest_file)
    print(s3_bucket)
    s3 = boto3.resource('s3')
    s3.Bucket(s3_bucket).upload_file(local_path + cl_manifest_file, s3_key_path_manifest_file + cl_manifest_file)

    print ('S3 URL Path to manifest file. ')
    print('\033[1m s3://' + s3_bucket + '/' + s3_key_path_manifest_file + cl_manifest_file + '\033[0m') 
    print ('\nAWS CLI s3 sync command to upload your images to S3 bucket. ')
    print ('\033[1m aws s3 sync ' + local_images_path + ' ' + s3_path + '\033[0m')
