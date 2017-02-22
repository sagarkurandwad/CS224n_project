import cPickle
import numpy as np
import os
import random
import matplotlib.pyplot as plt
import skimage.io as io

# add the "PythonAPI" dir to the path so that "pycocotools" can be found:
import sys
sys.path.append("/home/fregu856/CS224n/project/CS224n_project/coco/PythonAPI")
from pycocotools.coco import COCO

# add the "coco-caption" dir to the path so that "pycocoevalcap" can be found:
sys.path.append("/home/fregu856/CS224n/project/CS224n_project/coco/coco-caption")
from pycocoevalcap.eval import COCOEvalCap

from extract_img_features import extract_img_features

import json
from json import encoder
encoder.FLOAT_REPR = lambda o: format(o, '.3f')

def get_batches(model_obj):
    batch_size = model_obj.config.batch_size

    # group all caption ids in batches:
    batches_of_caption_ids = []
    for caption_length in model_obj.caption_length_2_no_of_captions:
        caption_ids = model_obj.caption_length_2_caption_ids[caption_length]
        # randomly shuffle the order of the caption ids:
        random.shuffle(caption_ids)
        no_of_captions = model_obj.caption_length_2_no_of_captions[caption_length]
        no_of_full_batches = int(no_of_captions/batch_size)

        # add all full batches to batches_of_caption_ids:
        for i in range(no_of_full_batches):
            batch_caption_ids = caption_ids[i*batch_size:(i+1)*batch_size]
            batches_of_caption_ids.append(batch_caption_ids)

        # get the remaining caption ids and add to batches_of_captions (not a
        # full batch, i.e, it will contain fewer than "batch_size" captions):
        #batch_caption_ids = caption_ids[no_of_full_batches*batch_size:]
        #batches_of_caption_ids.append(batch_caption_ids)

    # randomly shuffle the order of the batches:
    random.shuffle(batches_of_caption_ids)

    return batches_of_caption_ids

def get_batch_ph_data(model_obj, batch_caption_ids):
    # get the dimension parameters:
    batch_size = model_obj.config.batch_size
    img_dim = model_obj.config.img_dim
    caption_length = len(model_obj.train_caption_id_2_caption[batch_caption_ids[0]])

    captions = np.zeros((batch_size, caption_length))
    # (row i of captions will be the tokenized caption for ex i in the batch)
    img_vectors = np.zeros((batch_size, img_dim))
    # (row i of img_vectors will be the img feature vector for ex i in the batch)
    labels = -np.ones((batch_size, caption_length + 1))
    # (row i of labels will be the targets for ex i in the batch)

    # populate the return data:
    for i in range(len(batch_caption_ids)):
        caption_id = batch_caption_ids[i]
        img_id = model_obj.caption_id_2_img_id[caption_id]
        if img_id in model_obj.train_img_id_2_feature_vector:
            img_vector = model_obj.train_img_id_2_feature_vector[img_id]
        else:
            img_vector = np.zeros((1, img_dim))
        caption = model_obj.train_caption_id_2_caption[caption_id]

        captions[i] = caption
        img_vectors[i] = img_vector
        labels[i, 1:caption_length] = caption[1:]

        # example to explain labels:
        # caption == [<SOS>, a, cat, <EOS>]
        # caption_length == 4
        # labels[i] == [-1, -1, -1, -1, -1]
        # caption[1:] == [a, cat, <EOS>]
        # labels[i, 1:caption_length] = caption[1:] gives:
        # labels[i] == [-1, a, cat, <EOS>, -1]
        # corresponds to the input:
        # img, <SOS>, a, cat, <EOS>
        # img: no prediciton should be made (-1)
        # <SOS>: should predict a (a)
        # a: should predict cat (cat)
        # cat: should predict <EOS> (<EOS>)
        # <EOS>: no prediction should be made (-1)

    return captions, img_vectors, labels

def train_data_iterator(model_obj):
    # get the batches of caption ids:
    batches_of_caption_ids = get_batches(model_obj)

    for batch_of_caption_ids in batches_of_caption_ids:
        # get the batch's data in a format ready to be fed into the placeholders:
        captions, img_vectors, labels = get_batch_ph_data(model_obj,
                    batch_of_caption_ids)

        # yield the data to enable iteration (will be able to do:
        # for (captions, img_vector, labels) in train_data_iterator(config):)
        yield (captions, img_vectors, labels)

def detokenize_caption(tokenized_caption, vocabulary):
    caption_vector = []
    for word_index in tokenized_caption:
        word = vocabulary[word_index]
        caption_vector.append(word)

    # remove <SOS> and <EOS>:
    caption_vector.pop(0)
    caption_vector.pop()

    # turn the caption vector into a string:
    caption = " ".join(caption_vector)

    return caption

def evaluate_captions(captions_file):
    # define where the ground truth captions for the val imgs are located:
    true_captions_file = "coco/annotations/captions_val2014.json"

    coco = COCO(true_captions_file)
    cocoRes = coco.loadRes(captions_file)
    cocoEval = COCOEvalCap(coco, cocoRes)

    # set the imgs to be evaluated to the ones we have generated captions for:
    cocoEval.params["image_id"] = cocoRes.getImgIds()
    # evaluate the captions (compute metrics):
    cocoEval.evaluate()
    # get the dict containing all computed metrics and metric scores:
    results_dict = cocoEval.eval

    return results_dict

def plot_performance(model_dir):
    # load the saved performance data:
    metrics_per_epoch = cPickle.load(open("%s/eval_results/metrics_per_epoch"\
                % model_dir))
    loss_per_epoch = cPickle.load(open("%s/losses/loss_per_epoch" % model_dir))

    # separate the data for the different metrics:
    CIDEr_per_epoch = []
    Bleu_4_per_epoch = []
    ROUGE_L_per_epoch = []
    METEOR_per_epoch = []
    for epoch_metrics in metrics_per_epoch:
        CIDEr_per_epoch.append(epoch_metrics["CIDEr"])
        Bleu_4_per_epoch.append(epoch_metrics["Bleu_4"])
        ROUGE_L_per_epoch.append(epoch_metrics["ROUGE_L"])
        METEOR_per_epoch.append(epoch_metrics["METEOR"])

    # plot the loss vs epoch:
    plt.figure(1)
    plt.plot(loss_per_epoch, "k^")
    plt.plot(loss_per_epoch, "k")
    plt.ylabel("loss")
    plt.xlabel("epoch")
    plt.title("loss per epoch")
    plt.savefig("%s/plots/loss_per_epoch.png" % model_dir)

    # plot CIDEr vs epoch:
    plt.figure(2)
    plt.plot(CIDEr_per_epoch, "k^")
    plt.plot(CIDEr_per_epoch, "k")
    plt.ylabel("CIDEr")
    plt.xlabel("epoch")
    plt.title("CIDEr per epoch")
    plt.savefig("%s/plots/CIDEr_per_epoch.png" % model_dir)

    # plot Bleu_4 vs epoch:
    plt.figure(3)
    plt.plot(Bleu_4_per_epoch, "k^")
    plt.plot(Bleu_4_per_epoch, "k")
    plt.ylabel("Bleu_4")
    plt.xlabel("epoch")
    plt.title("Bleu_4 per epoch")
    plt.savefig("%s/plots/Bleu_4_per_epoch.png" % model_dir)

    # plot ROUGE_L vs epoch:
    plt.figure(4)
    plt.plot(ROUGE_L_per_epoch, "k^")
    plt.plot(ROUGE_L_per_epoch, "k")
    plt.ylabel("ROUGE_L")
    plt.xlabel("epoch")
    plt.title("ROUGE_L per epoch")
    plt.savefig("%s/plots/ROUGE_L_per_epoch.png" % model_dir)

    # plot METEOR vs epoch:
    plt.figure(5)
    plt.plot(METEOR_per_epoch, "k^")
    plt.plot(METEOR_per_epoch, "k")
    plt.ylabel("METEOR")
    plt.xlabel("epoch")
    plt.title("METEOR per epoch")
    plt.savefig("%s/plots/METEOR_per_epoch.png" % model_dir)

def compare_captions(model_dir, epoch):
    # define where the ground truth captions for the val imgs are located:
    true_captions_file = "coco/annotations/captions_val2014.json"

    coco = COCO(true_captions_file)
    # load the file containing all generated captions:
    cocoRes = coco.loadRes("%s/generated_captions/captions_%d.json"\
                % (model_dir, epoch))

    # get the img id of all imgs for which captions have been generated:
    img_ids = cocoRes.getImgIds()
    # choose one specific img:
    img_id = img_ids[175]

    # print all ground truth captions for the img:
    print "ground truth captions:"
    annIds = coco.getAnnIds(imgIds=img_id)
    anns = coco.loadAnns(annIds)
    coco.showAnns(anns)

    # print the generated caption for the img:
    print "generated caption:"
    annIds = cocoRes.getAnnIds(imgIds=img_id)
    anns = cocoRes.loadAnns(annIds)
    coco.showAnns(anns)

    # display the img:
    img = coco.loadImgs(img_id)[0]
    I = io.imread("coco/images/val/%s" % img["file_name"])
    plt.imshow(I)
    plt.axis('off')
    plt.show()

def map_img_id_2_file_name():
    img_id_2_file_name = {}

    train_captions_file = "coco/annotations/captions_train2014.json"
    train_coco = COCO(train_captions_file)

    val_captions_file = "coco/annotations/captions_val2014.json"
    val_coco = COCO(val_captions_file)

    val_img_ids = val_coco.getImgIds()
    val_imgs = val_coco.loadImgs(val_img_ids)
    for img_obj in val_imgs:
        file_name = img_obj["file_name"]
        img_id = img_obj["id"]
        img_id_2_file_name[img_id] = file_name

    train_img_ids = train_coco.getImgIds()
    train_imgs = train_coco.loadImgs(train_img_ids)
    for img_obj in train_imgs:
        file_name = img_obj["file_name"]
        img_id = img_obj["id"]
        img_id_2_file_name[img_id] = file_name

    cPickle.dump(img_id_2_file_name, open("coco/data/img_id_2_file_name", "wb"))

def main():
    map_img_id_2_file_name()

if __name__ == '__main__':
    main()
