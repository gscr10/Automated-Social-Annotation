# -*- coding: utf-8 -*-
#training the model.
#process--->1.load data(X:list of lint,y:int). 2.create session. 3.feed data. 4.training (5.validation) ,(6.prediction)
import tensorflow as tf
import numpy as np
import time
import os
import sys
from BiGRU_model import BiGRU

from data_util import load_data_multilabel_new,load_data_multilabel_new_k_fold,create_voabulary,create_voabulary_label,get_label_sim_matrix,get_label_sub_matrix
from tflearn.data_utils import pad_sequences
import word2vec
import pickle
import random as rn
import statistics

#tf.reset_default_graph()

# Setting the seed for numpy-generated random numbers
#np.random.seed(1)

# Setting the seed for python random numbers
#rn.seed(1)

# Setting the graph-level random seed.
#tf.set_random_seed(1)

#start time
start_time = time.time()
#configuration
FLAGS=tf.app.flags.FLAGS
tf.app.flags.DEFINE_string("dataset","bibsonomy-clean","dataset to chose") # two options: "bibsonomy-clean" and "zhihu-sample"
#tf.app.flags.DEFINE_string("dataset","zhihu-sample","dataset to chose") # two options: "bibsonomy-clean" and "zhihu-sample"

tf.app.flags.DEFINE_float("learning_rate",0.01,"learning rate") #TODO 0.01
tf.app.flags.DEFINE_integer("batch_size", 128, "Batch size for training/evaluating.") #批处理的大小 32-->128 #TODO
tf.app.flags.DEFINE_integer("decay_steps", 6000, "how many steps before decay learning rate.") #6000批处理的大小 32-->128
tf.app.flags.DEFINE_float("decay_rate", 1.0, "Rate of decay for learning rate.") #0.87一次衰减多少
tf.app.flags.DEFINE_string("ckpt_dir","checkpoint_hier_atten_title4/","checkpoint location for the model")
tf.app.flags.DEFINE_integer("sequence_length",300,"max sentence length")
tf.app.flags.DEFINE_integer("embed_size",100,"embedding size")
tf.app.flags.DEFINE_boolean("is_training",True,"is traning.true:tranining,false:testing/inference")
tf.app.flags.DEFINE_integer("num_epochs",100,"number of epochs to run.")
tf.app.flags.DEFINE_integer("validate_every", 1, "Validate every validate_every epochs.") #每10轮做一次验证
tf.app.flags.DEFINE_integer("validate_step", 1000, "how many step to validate.") #1500做一次检验 TODO [this validation is also for decaying the learning rate based on the evaluation loss]
tf.app.flags.DEFINE_boolean("use_embedding",True,"whether to use embedding or not.")
tf.app.flags.DEFINE_float("label_sim_threshold",0,"similarity value below this threshold will be set as 0.")
tf.app.flags.DEFINE_float("lambda_sim",0,"the lambda for sim-loss.")
tf.app.flags.DEFINE_float("lambda_sub",0,"the lambda for sub-loss.")
#tf.app.flags.DEFINE_string("cache_path","text_cnn_checkpoint/data_cache.pik","checkpoint location for the model")
tf.app.flags.DEFINE_boolean("dynamic_sem",False,"whether to finetune the sim and sub matrices during training.")
tf.app.flags.DEFINE_boolean("dynamic_sem_l2",False,"whether to L2 regularise while finetuning the sim and sub matrices during training.")

#for simulating missing labels
tf.app.flags.DEFINE_float("keep_label_percent",1,"the percentage of labels in each instance of the training data to be randomly reserved, the rest labels are dropped to simulate the missing label scenario.")

#for both tuning and final testing
tf.app.flags.DEFINE_string("training_data_path_bib","../datasets/bibsonomy_preprocessed_merged_final.txt","path of traning data.") # for bibsonomy dataset
tf.app.flags.DEFINE_string("training_data_path_zhihu","../datasets/question_train_set_cleaned_150000.txt","path of traning data.") # for zhihu dataset
tf.app.flags.DEFINE_string("training_data_path_cua","../datasets/citeulike_a_cleaned_th10.txt","path of traning data.") # for cua dataset
tf.app.flags.DEFINE_string("training_data_path_cut","../datasets/citeulike_t_cleaned_th10.txt","path of traning data.") # for cut dataset

tf.app.flags.DEFINE_float("valid_portion",0.1,"dev set or test set portion") # this is only valid when kfold is -1, which means we hold out a fixed set for validation. If we set this as 0.1, then there will be 0.81 0.09 0.1 for train-valid-test split (same as the split of 10-fold cross-validation); if we set this as 0.111, then there will be 0.8 0.1 0.1 for train-valid-test split.
tf.app.flags.DEFINE_float("test_portion",0.1,"held-out evaluation: test set portion")
tf.app.flags.DEFINE_integer("kfold",10,"k-fold cross-validation") # if k is -1, then not using kfold cross-validation

tf.app.flags.DEFINE_string("marking_id","","an marking_id (or group_id) for better marking: will show in the output filenames")

tf.app.flags.DEFINE_string("word2vec_model_path_bib","../embeddings/word-bib.bin-100","word2vec's vocabulary and vectors for inputs")
tf.app.flags.DEFINE_string("word2vec_model_path_zhihu","../embeddings/word150000.bin-100","word2vec's vocabulary and vectors")
tf.app.flags.DEFINE_string("word2vec_model_path_cua","../embeddings/word-citeulike-a.bin-100","word2vec's vocabulary and vectors")
tf.app.flags.DEFINE_string("word2vec_model_path_cut","../embeddings/word-citeulike-t-th10.bin-100","word2vec's vocabulary and vectors")

tf.app.flags.DEFINE_string("emb_model_path_bib","../embeddings/tag-all-bib-final.bin-300","pre-trained model from bibsonomy labels")
tf.app.flags.DEFINE_string("emb_model_path_zhihu","../embeddings/tag_all.bin-300","pre-trained model from zhihu labels")
tf.app.flags.DEFINE_string("emb_model_path_cua","../embeddings/tag-citeulike-a-all.bin-300","pre-trained model from cua labels")
tf.app.flags.DEFINE_string("emb_model_path_cut","../embeddings/tag-citeulike-t-all.bin-300","pre-trained model from cut labels")

tf.app.flags.DEFINE_string("kb_dbpedia_path","../knowledge_bases/bibsonomy_skos_withredir_pw_candidts_all_labelled.csv","labels matched to DBpedia skos and redir relations") # for bibsonomy dataset
tf.app.flags.DEFINE_string("kb_MCG_path","../knowledge_bases/bibsonomy_mcg5_cleaned.csv","labels matched to Microsoft Concept Graph relations") # for bibsonomy dataset
tf.app.flags.DEFINE_string("kb_zhihu","../knowledge_bases/zhihu_kb.csv","label relations for zhihu data") # for zhihu dataset
tf.app.flags.DEFINE_string("kb_cua","../knowledge_bases/citeulike-a-mcg-kb.csv","label relations for cua data") # for zhihu dataset
tf.app.flags.DEFINE_string("kb_cut","../knowledge_bases/citeulike-t-mcg-kb.csv","label relations for cut data") # for cut dataset

tf.app.flags.DEFINE_boolean("multi_label_flag",True,"use multi label or single label.")
#tf.app.flags.DEFINE_integer("num_sentences", 10, "number of sentences in the document")
tf.app.flags.DEFINE_integer("hidden_size",100,"hidden size") # same as embedding size
tf.app.flags.DEFINE_boolean("weight_decay_testing",True,"weight decay based on validation data.") # decay the weight by half if validation loss increases.
tf.app.flags.DEFINE_boolean("report_rand_pred",True,"report prediction for qualitative analysis")
tf.app.flags.DEFINE_float("early_stop_lr",0.00002,"early stop point when learning rate is belwo is threshold") #0.00002
tf.app.flags.DEFINE_float("ave_labels_per_doc",11.59,"average labels per document for bibsonomy dataset")
tf.app.flags.DEFINE_integer("topk",5,"using top-k predicted labels for evaluation")

#1.load data(X:list of lint,y:int). 2.create session. 3.feed data. 4.training (5.validation) ,(6.prediction)
def main(_):
    #1.load data(X:list of lint,y:int).
    #if os.path.exists(FLAGS.cache_path):  # 如果文件系统中存在，那么加载故事（词汇表索引化的）
    #    with open(FLAGS.cache_path, 'r') as data_f:
    #        trainX, trainY, testX, testY, vocabulary_index2word=pickle.load(data_f)
    #        vocab_size=len(vocabulary_index2word)
    #else:
    
    # assign data specific variables:
    if FLAGS.dataset == "bibsonomy-clean":
        word2vec_model_path = FLAGS.word2vec_model_path_bib
        traning_data_path = FLAGS.training_data_path_bib
        emb_model_path = FLAGS.emb_model_path_bib
        
        vocabulary_word2index_label,vocabulary_index2word_label = create_voabulary_label(voabulary_label=traning_data_path, name_scope=FLAGS.dataset + "-BiGRU") # keep a distinct name scope for each model and each dataset.
        
        #similarity relations: using self-trained label embedding
        label_sim_mat = get_label_sim_matrix(vocabulary_index2word_label,emb_model_path,name_scope=FLAGS.dataset)
        
        #subsumption relations: using external knowledge bases
        #label_sub_mat = get_label_sub_matrix(vocabulary_word2index_label,kb_path=FLAGS.kb_dbpedia_path,name_scope='dbpedia');print('using DBpedia relations') #use_dbpedia
        label_sub_mat = get_label_sub_matrix(vocabulary_word2index_label,kb_path=FLAGS.kb_MCG_path,name_scope='bib');print('using MCG relations') # 101084
        
        #configurations:
        FLAGS.batch_size = 128
        FLAGS.sequence_length = 300
        FLAGS.ave_labels_per_doc = 11.59
        #FLAGS.lambda_sim = 0 # lambda1
        #FLAGS.lambda_sub = 0 # lambda2
        FLAGS.topk = 11
        
    elif FLAGS.dataset == "zhihu-sample":
        word2vec_model_path = FLAGS.word2vec_model_path_zhihu
        traning_data_path = FLAGS.training_data_path_zhihu
        emb_model_path = FLAGS.emb_model_path_zhihu
        
        vocabulary_word2index_label,vocabulary_index2word_label = create_voabulary_label(voabulary_label=traning_data_path, name_scope=FLAGS.dataset + "-BiGRU")
        
        #similarity relations: using self-trained label embedding
        label_sim_mat = get_label_sim_matrix(vocabulary_index2word_label,emb_model_path,name_scope=FLAGS.dataset)
        
        #subsumption relations: using zhihu crowdsourced relations
        label_sub_mat = get_label_sub_matrix(vocabulary_word2index_label,kb_path=FLAGS.kb_zhihu,name_scope='zhihu');print('using zhihu relations')
        
        #configurations:
        #FLAGS.batch_size = 1024
        FLAGS.sequence_length = 100
        FLAGS.ave_labels_per_doc = 2.45
        #FLAGS.lambda_sim = 0 # lambda1
        #FLAGS.lambda_sub = 0 # lambda2
        FLAGS.topk = 2
    
    elif FLAGS.dataset == "citeulike-a-clean":
        word2vec_model_path = FLAGS.word2vec_model_path_cua
        traning_data_path = FLAGS.training_data_path_cua
        emb_model_path = FLAGS.emb_model_path_cua
        
        vocabulary_word2index_label,vocabulary_index2word_label = create_voabulary_label(voabulary_label=traning_data_path, name_scope=FLAGS.dataset + "-BiGRU")
        
        #similarity relations: using self-trained label embedding
        label_sim_mat = get_label_sim_matrix(vocabulary_index2word_label,emb_model_path,name_scope=FLAGS.dataset)
        
        #subsumption relations: using zhihu crowdsourced relations
        label_sub_mat = get_label_sub_matrix(vocabulary_word2index_label,kb_path=FLAGS.kb_cua,name_scope='cua');print('using cua-mcg relations')
        
        #configurations:
        FLAGS.batch_size = 128
        FLAGS.sequence_length = 300
        FLAGS.ave_labels_per_doc = 11.6
        #FLAGS.lambda_sim = 0 # lambda1
        #FLAGS.lambda_sub = 0 # lambda2
        FLAGS.topk = 50
        #FLAGS.early_stop_lr = 0.001
    
    elif FLAGS.dataset == "citeulike-t-clean":
        word2vec_model_path = FLAGS.word2vec_model_path_cut
        traning_data_path = FLAGS.training_data_path_cut
        emb_model_path = FLAGS.emb_model_path_cut
        
        vocabulary_word2index_label,vocabulary_index2word_label = create_voabulary_label(voabulary_label=traning_data_path, name_scope=FLAGS.dataset + "-BiGRU", label_freq_th = 0)
        
        #similarity relations: using self-trained label embedding
        label_sim_mat = get_label_sim_matrix(vocabulary_index2word_label,emb_model_path,name_scope=FLAGS.dataset)
        
        #subsumption relations: using external knowledge bases
        label_sub_mat = get_label_sub_matrix(vocabulary_word2index_label,kb_path=FLAGS.kb_cut,name_scope='cut');print('using cut-mcg relations')
        
        #configurations:
        FLAGS.batch_size = 128
        FLAGS.sequence_length = 300
        FLAGS.ave_labels_per_doc = 7.68
        #FLAGS.lambda_sim = 0 # lambda1
        #FLAGS.lambda_sub = 0 # lambda2
        FLAGS.topk = 50
        #FLAGS.early_stop_lr = 0.001
        
    else:
        print("dataset unrecognisable")
        sys.exit()
    
    num_classes=len(vocabulary_word2index_label)
    print(vocabulary_index2word_label[0],vocabulary_index2word_label[1])
    trainX, trainY, testX, testY = None, None, None, None
    vocabulary_word2index, vocabulary_index2word = create_voabulary(word2vec_model_path,name_scope=FLAGS.dataset + "-BiGRU")
    
    # check sim and sub relations
    print("label_sim_mat:",label_sim_mat.shape)
    print("label_sim_mat[0]:",label_sim_mat[0])
    print("label_sub_mat:",label_sub_mat.shape)
    print("label_sub_mat[0]:",label_sub_mat[0])
    print("label_sub_mat_sum:",np.sum(label_sub_mat))
    
    vocab_size = len(vocabulary_word2index)
    print("vocab_size:",vocab_size)
    
    # choosing whether to use k-fold cross-validation or hold-out validation
    if FLAGS.kfold == -1: # hold-out
        train, valid, test = load_data_multilabel_new(vocabulary_word2index, vocabulary_word2index_label,keep_label_percent=FLAGS.keep_label_percent,valid_portion=FLAGS.valid_portion,test_portion=FLAGS.test_portion,multi_label_flag=FLAGS.multi_label_flag,traning_data_path=traning_data_path) 
        # here train, test are tuples; turn train into trainlist.
        trainlist, validlist, testlist = list(), list(), list()
        trainlist.append(train)
        validlist.append(valid)
        testlist.append(test)
    else: # k-fold
        trainlist, validlist, testlist = load_data_multilabel_new_k_fold(vocabulary_word2index, vocabulary_word2index_label,keep_label_percent=FLAGS.keep_label_percent,kfold=FLAGS.kfold,test_portion=FLAGS.test_portion,multi_label_flag=FLAGS.multi_label_flag,traning_data_path=traning_data_path)
        # here trainlist, testlist are list of tuples.
    # get and pad testing data: there is only one testing data, but kfold training and validation data
    assert len(testlist) == 1
    testX, testY = testlist[0]
    testX = pad_sequences(testX, maxlen=FLAGS.sequence_length, value=0.)  # padding to max length
    
    #2.create session.
    config=tf.ConfigProto()
    config.gpu_options.allow_growth=False
    with tf.Session(config=config) as sess:
        model=BiGRU(num_classes, FLAGS.learning_rate, FLAGS.batch_size, FLAGS.decay_steps, FLAGS.decay_rate, FLAGS.sequence_length, vocab_size, FLAGS.embed_size, FLAGS.is_training,FLAGS.lambda_sim,FLAGS.lambda_sub,FLAGS.dynamic_sem,FLAGS.dynamic_sem_l2,multi_label_flag=FLAGS.multi_label_flag)
        
        num_runs = len(trainlist)
        #validation results variables
        valid_loss, valid_acc_th,valid_prec_th,valid_rec_th,valid_fmeasure_th,valid_hamming_loss_th,valid_acc_topk,valid_prec_topk,valid_rec_topk,valid_fmeasure_topk,valid_hamming_loss_topk = [0]*num_runs,[0]*num_runs,[0]*num_runs,[0]*num_runs,[0]*num_runs,[0]*num_runs,[0]*num_runs,[0]*num_runs,[0]*num_runs,[0]*num_runs,[0]*num_runs # initialise the testing result lists
        final_valid_loss,final_valid_acc_th,final_valid_prec_th,final_valid_rec_th,final_valid_fmeasure_th,final_valid_hamming_loss_th,final_valid_acc_topk,final_valid_prec_topk,final_valid_rec_topk,final_valid_fmeasure_topk,final_valid_hamming_loss_topk =0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0
        min_valid_loss,min_valid_acc_th,min_valid_prec_th,min_valid_rec_th,min_valid_fmeasure_th,min_valid_hamming_loss_th,min_valid_acc_topk,min_valid_prec_topk,min_valid_rec_topk,min_valid_fmeasure_topk,min_valid_hamming_loss_topk =0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0
        max_valid_loss,max_valid_acc_th,max_valid_prec_th,max_valid_rec_th,max_valid_fmeasure_th,max_valid_hamming_loss_th,max_valid_acc_topk,max_valid_prec_topk,max_valid_rec_topk,max_valid_fmeasure_topk,max_valid_hamming_loss_topk =0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0
        std_valid_loss,std_valid_acc_th,std_valid_prec_th,std_valid_rec_th,std_valid_fmeasure_th,std_valid_hamming_loss_th,std_valid_acc_topk,std_valid_prec_topk,std_valid_rec_topk,std_valid_fmeasure_topk,std_valid_hamming_loss_topk =0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0
        #testing results variables
        test_loss, test_acc_th,test_prec_th,test_rec_th,test_fmeasure_th,test_hamming_loss_th,test_acc_topk,test_prec_topk,test_rec_topk,test_fmeasure_topk,test_hamming_loss_topk = [0]*num_runs,[0]*num_runs,[0]*num_runs,[0]*num_runs,[0]*num_runs,[0]*num_runs,[0]*num_runs,[0]*num_runs,[0]*num_runs,[0]*num_runs,[0]*num_runs # initialise the testing result lists
        final_test_loss,final_test_acc_th,final_test_prec_th,final_test_rec_th,final_test_fmeasure_th,final_test_hamming_loss_th,final_test_acc_topk,final_test_prec_topk,final_test_rec_topk,final_test_fmeasure_topk,final_test_hamming_loss_topk =0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0
        min_test_loss,min_test_acc_th,min_test_prec_th,min_test_rec_th,min_test_fmeasure_th,min_test_hamming_loss_th,min_test_acc_topk,min_test_prec_topk,min_test_rec_topk,min_test_fmeasure_topk,min_test_hamming_loss_topk =0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0
        max_test_loss,max_test_acc_th,max_test_prec_th,max_test_rec_th,max_test_fmeasure_th,max_test_hamming_loss_th,max_test_acc_topk,max_test_prec_topk,max_test_rec_topk,max_test_fmeasure_topk,max_test_hamming_loss_topk =0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0
        std_test_loss,std_test_acc_th,std_test_prec_th,std_test_rec_th,std_test_fmeasure_th,std_test_hamming_loss_th,std_test_acc_topk,std_test_prec_topk,std_test_rec_topk,std_test_fmeasure_topk,std_test_hamming_loss_topk =0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0
        #output variables
        output_valid = ""
        output_test = ""
        output_csv_valid = "fold,loss,hamming_loss,acc,prec,rec,f1,acc@k,hamming_loss@k,prec@k,rec@k,f1@k"
        output_csv_test = "fold,loss,hamming_loss,acc,prec,rec,f1,acc@k,hamming_loss@k,prec@k,rec@k,f1@k"
        # start iterating over k-folds for training and testing        
        num_run = 0
        time_train = [0]*num_runs # get time spent in training
        for train, valid in zip(trainlist, validlist):
            print('\n--RUN',num_run,'START--\n')
            start_time_train = time.time() # staring time in training
            # k-fold dataset creation
            trainX, trainY = train
            validX, validY = valid
            # Data preprocessing.Sequence padding
            print("start padding & transform to one hot...")
            trainX = pad_sequences(trainX, maxlen=FLAGS.sequence_length, value=0.)  # padding to max length
            validX = pad_sequences(validX, maxlen=FLAGS.sequence_length, value=0.)  # padding to max length
            #with open(FLAGS.cache_path, 'w') as data_f: #save data to cache file, so we can use it next time quickly.
            #    pickle.dump((trainX,trainY,testX,testY,vocabulary_index2word),data_f)
            print("trainX[0]:", trainX[0]) ;#print("trainY[0]:", trainY[0])
            #print("validX[0]:", validX[0])
            # Converting labels to binary vectors
            print("end padding & transform to one hot...")

            saver=tf.train.Saver()
            if os.path.exists(FLAGS.ckpt_dir+"checkpoint"):
                print("Restoring Variables from Checkpoint")
                saver.restore(sess,tf.train.latest_checkpoint(FLAGS.ckpt_dir))
            else:
                print('Initializing Variables')
                sess.run(tf.global_variables_initializer()) # which initialise parameters
                if FLAGS.use_embedding: #load pre-trained word embedding
                    assign_pretrained_word_embedding(sess, vocabulary_index2word, vocab_size, model,num_run,word2vec_model_path=word2vec_model_path)
                if FLAGS.dynamic_sem:
                    assign_sim_sub_matrices(sess,FLAGS.lambda_sim,FLAGS.lambda_sub,label_sim_mat,label_sub_mat,model)    
            #print('loaded Uw', sess.run(model.context_vecotor_word))
            curr_epoch=sess.run(model.epoch_step) # after restoring, the parameters are initialised.
            #3.feed data & training
            number_of_training_data=len(trainX)
            print("number_of_training_data:",number_of_training_data)
            previous_eval_loss=10000
            #previous_eval_fmeasure=0
            best_eval_loss=10000
            batch_size=FLAGS.batch_size
            curr_step = curr_epoch*batch_size
            # iterating over epoches
            for epoch in range(curr_epoch,FLAGS.num_epochs):
                if epoch%10==0:
                    display_results_bool=True
                else:
                    display_results_bool=False            
                loss, acc, counter = 0.0, 0.0, 0
                for start, end in zip(range(0, number_of_training_data, batch_size),range(batch_size, number_of_training_data, batch_size)): # might have lost a very little part of data (105 out of 15849) here which is the mod after dividing the batch_size
                    if num_run==0 and epoch==0 and counter==0: #num_run for folds, epoch for iterations, counter for batches
                        print("trainX[start:end]:",trainX[start:end]);#print("trainY[start:end]:",trainY[start:end])
                    feed_dict = {model.input_x: trainX[start:end],model.dropout_keep_prob: 0.5}
                    if not FLAGS.multi_label_flag:
                        feed_dict[model.input_y] = trainY[start:end]
                    else:
                        feed_dict[model.input_y_multilabel]=trainY[start:end]
                    feed_dict[model.label_sim_matrix_static]=label_sim_mat
                    feed_dict[model.label_sub_matrix_static]=label_sub_mat
                    # now we start training
                    curr_summary_str,curr_summary_l_epoch,curr_loss,curr_acc,label_sim_mat_updated,label_sub_mat_updated,_=sess.run([model.training_loss,model.training_loss_per_epoch,model.loss_val,model.accuracy,model.label_sim_matrix,model.label_sub_matrix,model.train_op],feed_dict)
                    
                    if FLAGS.dynamic_sem == True:
                        # # check the amount of changes
                        #print('sim_absolute_update_sum:',np.sum(np.absolute(label_sim_mat - label_sim_mat_updated)))
                        #print('sub_absolute_update_sum:',np.sum(np.absolute(label_sub_mat - label_sub_mat_updated)))
                        label_sim_mat = label_sim_mat_updated
                        label_sub_mat = label_sub_mat_updated
                        # print("label_sim_mat[0]-updated:",label_sim_mat[0])
                        # print("label_sub_mat[0]-updated:",label_sub_mat[0])
                        
                    curr_step=curr_step+1
                    model.writer.add_summary(curr_summary_str,curr_step)
                    if counter==0:
                        model.writer.add_summary(curr_summary_l_epoch,epoch) # this is the training loss per epoch
                    loss,counter,acc=loss+curr_loss,counter+1,acc+curr_acc
                    # output every 50 batches
                    if counter %50==0:
                        print("Bi-GRU==>Epoch %d\tBatch %d\tTrain Loss:%.3f\tTrain Accuracy:%.3f" %(epoch,counter,loss/float(counter),acc/float(counter))) #tTrain Accuracy:%.3f---》acc/float(counter)
                    
                    # using validation set to calculate validation loss, then to see whether we need to decay the learning rate.
                    # and the decay of learning rate is used for early stopping.
                    if FLAGS.weight_decay_testing:                    
                        ##VALIDATION VALIDATION VALIDATION PART######################################################################################################
                        # to check whether the evaluation loss on testing data is decreasing, if not then half the learning rate: so the update of weights gets halved.
                        if FLAGS.batch_size!=0 and (start%(FLAGS.validate_step*FLAGS.batch_size)==0): #(epoch % FLAGS.validate_every) or  if epoch % FLAGS.validate_every == 0:
                            print(epoch, FLAGS.validate_step, FLAGS.batch_size) # here shows only when start being 0, the program goes under this condition. This is okay as our dataset is not too large.
                            #eval_loss, eval_acc = do_eval(sess, model, testX, testY, batch_size,vocabulary_index2word_label)
                            #eval_loss, eval_acc,eval_prec,eval_rec,eval_fmeasure = do_eval_multilabel(sess, model, tag_pair_matrix, label_sim_matrix, testX, testY, batch_size,vocabulary_index2word_label,epoch,number_labels_to_predict=11)
                            eval_loss,_,_,_,_,_,_,_,_,_,_ = do_eval_multilabel_threshold(sess,model,label_sim_mat,label_sub_mat,validX,validY,batch_size,vocabulary_index2word,vocabulary_index2word_label,epoch,threshold=0.5,display_results_bool=False,hamming_q=FLAGS.ave_labels_per_doc,top_number=FLAGS.topk,record_to_tensorboard=False) # here we use validation data [not testing data!] # do not record this to tensorboard
                            print("validation.part. previous_eval_loss:", previous_eval_loss,";current_eval_loss:", eval_loss)
                            #print("validation.part. previous_eval_fmeasure:", previous_eval_fmeasure,";current_eval_fmeasure:", eval_fmeasure)
                            if eval_loss > previous_eval_loss: #if loss is not decreasing
                            #if eval_fmeasure < previous_eval_fmeasure: # if f-measure is not increasing
                            # reduce the learning rate by a factor of 0.5
                                print("Bi-GRU==>validation.part.going to reduce the learning rate.")
                                learning_rate1 = sess.run(model.learning_rate)
                                lrr=sess.run([model.learning_rate_decay_half_op])
                                learning_rate2 = sess.run(model.learning_rate) # the new learning rate
                                print("Bi-GRU==>validation.part.learning_rate_original:", learning_rate1, " ;learning_rate_new:",learning_rate2)
                            previous_eval_loss = eval_loss
                            #previous_eval_fmeasure = eval_fmeasure
                        ##VALIDATION VALIDATION VALIDATION PART######################################################################################################

                #epoch increment
                print("going to increment epoch counter....")
                sess.run(model.epoch_increment)
            
                # 4.show validation results [not testing results!]
                if epoch % FLAGS.validate_every==0:
                    if epoch%50 == 0 and epoch != 0:
                        display_results_bool=True
                    else:
                        display_results_bool=False
                    eval_loss,eval_acc_th,eval_prec_th,eval_rec_th,eval_fmeasure_th,eval_hamming_loss_th,eval_acc_topk,eval_prec_topk,eval_rec_topk,eval_fmeasure_topk,eval_hamming_loss_topk = do_eval_multilabel_threshold(sess,model,label_sim_mat,label_sub_mat,validX,validY,batch_size,vocabulary_index2word,vocabulary_index2word_label,epoch,threshold=0.5,display_results_bool=display_results_bool,hamming_q=FLAGS.ave_labels_per_doc,top_number=FLAGS.topk,record_to_tensorboard=True)
                    print('lambda_sim', FLAGS.lambda_sim, 'lambda_sub', FLAGS.lambda_sub)
                    print("Bi-GRU==>Epoch %d Validation Loss:%.3f\tValidation Accuracy: %.3f\tValidation Hamming Loss: %.3f\tValidation Precision: %.3f\tValidation Recall: %.3f\tValidation F-measure: %.3f\tValidation Accuracy@k: %.3f\tValidation Hamming Loss@k: %.3f\tValidation Precision@k: %.3f\tValidation Recall@k: %.3f\tValidation F-measure@k: %.3f" % (epoch,eval_loss,eval_acc_th,eval_hamming_loss_th,eval_prec_th,eval_rec_th,eval_fmeasure_th,eval_acc_topk,eval_hamming_loss_topk,eval_prec_topk,eval_rec_topk,eval_fmeasure_topk))
                                            
                    #save model to checkpoint
                    #save_path=FLAGS.ckpt_dir+"model.ckpt"
                    #saver.save(sess,save_path,global_step=epoch)
                current_learning_rate = sess.run(model.learning_rate)    
                if current_learning_rate<FLAGS.early_stop_lr: # 0.00002
                    break
            
            time_train[num_run] = time.time() - start_time_train # store the training time for this fold to the list time_train().
            
            # 5.report validation results
            valid_loss[num_run], valid_acc_th[num_run],valid_prec_th[num_run],valid_rec_th[num_run],valid_fmeasure_th[num_run],valid_hamming_loss_th[num_run],valid_acc_topk[num_run],valid_prec_topk[num_run],valid_rec_topk[num_run],valid_fmeasure_topk[num_run],valid_hamming_loss_topk[num_run] = do_eval_multilabel_threshold(sess,model,label_sim_mat,label_sub_mat,validX,validY,batch_size,vocabulary_index2word,vocabulary_index2word_label,epoch,threshold=0.5,display_results_bool=True,hamming_q=FLAGS.ave_labels_per_doc,top_number=FLAGS.topk,record_to_tensorboard=False)
            print("Bi-GRU==>Run %d Validation results:%.3f\tValidation Accuracy: %.3f\tValidation Hamming Loss: %.3f\tValidation Precision: %.3f\tValidation Recall: %.3f\tValidation F-measure: %.3f\tValidation Accuracy@k: %.3f\tValidation Hamming Loss@k: %.3f\tValidation Precision@k: %.3f\tValidation Recall@k: %.3f\tValidation F-measure@k: %.3f" % (num_run,valid_loss[num_run],valid_acc_th[num_run],valid_hamming_loss_th[num_run],valid_prec_th[num_run],valid_rec_th[num_run],valid_fmeasure_th[num_run],valid_acc_topk[num_run],valid_hamming_loss_topk[num_run],valid_prec_topk[num_run],valid_rec_topk[num_run],valid_fmeasure_topk[num_run]))
            output_valid = output_valid + "\n" + "Bi-GRU==>Run %d Validation results Validation Loss:%.3f\tValidation Accuracy: %.3f\tValidation Hamming Loss: %.3f\tValidation Precision: %.3f\tValidation Recall: %.3f\tValidation F-measure: %.3f\tValidation Accuracy@k: %.3f\tValidation Hamming Loss@k: %.3f\tValidation Precision@k: %.3f\tValidation Recall@k: %.3f\tValidation F-measure@k: %.3f" % (num_run,valid_loss[num_run],valid_acc_th[num_run],valid_hamming_loss_th[num_run],valid_prec_th[num_run],valid_rec_th[num_run],valid_fmeasure_th[num_run],valid_acc_topk[num_run],valid_hamming_loss_topk[num_run],valid_prec_topk[num_run],valid_rec_topk[num_run],valid_fmeasure_topk[num_run]) + "\n" # also output the results of each run.
            output_csv_valid = output_csv_valid + "\n" + str(num_run) + "," + str(valid_loss[num_run]) + "," + str(valid_hamming_loss_th[num_run]) + "," + str(valid_acc_th[num_run]) + "," + str(valid_prec_th[num_run]) + "," + str(valid_rec_th[num_run]) + "," + str(valid_fmeasure_th[num_run]) + "," + str(valid_acc_topk[num_run]) + "," + str(valid_hamming_loss_topk[num_run]) + "," + str(valid_prec_topk[num_run]) + "," + str(valid_rec_topk[num_run]) + "," + str(valid_fmeasure_topk[num_run])
            
            # 6.here we use the testing data, to report testing results
            test_loss[num_run], test_acc_th[num_run],test_prec_th[num_run],test_rec_th[num_run],test_fmeasure_th[num_run],test_hamming_loss_th[num_run],test_acc_topk[num_run],test_prec_topk[num_run],test_rec_topk[num_run],test_fmeasure_topk[num_run],test_hamming_loss_topk[num_run] = do_eval_multilabel_threshold(sess,model,label_sim_mat,label_sub_mat,testX,testY,batch_size,vocabulary_index2word,vocabulary_index2word_label,epoch,threshold=0.5,display_results_bool=True,hamming_q=FLAGS.ave_labels_per_doc,top_number=FLAGS.topk,record_to_tensorboard=False)
            print("Bi-GRU==>Run %d Test results Test Loss:%.3f\tValidation Accuracy: %.3f\tValidation Hamming Loss: %.3f\tValidation Precision: %.3f\tValidation Recall: %.3f\tValidation F-measure: %.3f\tValidation Accuracy@k: %.3f\tValidation Hamming Loss@k: %.3f\tValidation Precision@k: %.3f\tValidation Recall@k: %.3f\tValidation F-measure@k: %.3f" % (num_run,test_loss[num_run],test_acc_th[num_run],test_hamming_loss_th[num_run],test_prec_th[num_run],test_rec_th[num_run],test_fmeasure_th[num_run],test_acc_topk[num_run],test_hamming_loss_topk[num_run],test_prec_topk[num_run],test_rec_topk[num_run],test_fmeasure_topk[num_run]))
            output_test = output_test + "\n" + "Bi-GRU==>Run %d Test results Validation Loss:%.3f\tValidation Accuracy: %.3f\tValidation Hamming Loss: %.3f\tValidation Precision: %.3f\tValidation Recall: %.3f\tValidation F-measure: %.3f\tValidation Accuracy@k: %.3f\tValidation Hamming Loss@k: %.3f\tValidation Precision@k: %.3f\tValidation Recall@k: %.3f\tValidation F-measure@k: %.3f" % (num_run,test_loss[num_run],test_acc_th[num_run],test_hamming_loss_th[num_run],test_prec_th[num_run],test_rec_th[num_run],test_fmeasure_th[num_run],test_acc_topk[num_run],test_hamming_loss_topk[num_run],test_prec_topk[num_run],test_rec_topk[num_run],test_fmeasure_topk[num_run]) + "\n" # also output the results of each run.
            output_csv_test = output_csv_test + "\n" + str(num_run) + "," + str(test_loss[num_run]) + "," + str(test_hamming_loss_th[num_run]) + "," + str(test_acc_th[num_run]) +  "," + str(test_prec_th[num_run]) + "," + str(test_rec_th[num_run]) + "," + str(test_fmeasure_th[num_run]) + "," + str(test_acc_topk[num_run]) + "," + str(test_hamming_loss_topk[num_run]) + "," + str(test_prec_topk[num_run]) + "," + str(test_rec_topk[num_run]) + "," + str(test_fmeasure_topk[num_run])
                
            print('lambda_sim', FLAGS.lambda_sim, 'lambda_sub', FLAGS.lambda_sub)
            print("--- This fold, run %s, took %s seconds ---" % (num_run, time_train[num_run]))

            prediction_str = ""
            # output final predictions for qualitative analysis
            if FLAGS.report_rand_pred == True:
                prediction_str = display_for_qualitative_evaluation(sess,model,label_sim_mat,label_sub_mat,testX,testY,batch_size,vocabulary_index2word,vocabulary_index2word_label,threshold=0.5)
            # update the num_run
            num_run=num_run+1
                
    print('\n--Final Results--\n')
    print('lambda_sim', FLAGS.lambda_sim, 'lambda_sub', FLAGS.lambda_sub)
    
    # 7. report min, max, std, average for the validation results
    min_valid_loss = min(valid_loss)
    min_valid_acc_th = min(valid_acc_th)
    min_valid_prec_th = min(valid_prec_th)
    min_valid_rec_th = min(valid_rec_th)
    min_valid_fmeasure_th = min(valid_fmeasure_th)
    min_valid_hamming_loss_th = min(valid_hamming_loss_th)
    min_valid_acc_topk = min(valid_acc_topk)
    min_valid_prec_topk = min(valid_prec_topk)
    min_valid_rec_topk = min(valid_rec_topk)
    min_valid_fmeasure_topk = min(valid_fmeasure_topk)
    min_valid_hamming_loss_topk = min(valid_hamming_loss_topk)
    
    max_valid_loss = max(valid_loss)
    max_valid_acc_th = max(valid_acc_th)
    max_valid_prec_th = max(valid_prec_th)
    max_valid_rec_th = max(valid_rec_th)
    max_valid_fmeasure_th = max(valid_fmeasure_th)
    max_valid_hamming_loss_th = max(valid_hamming_loss_th)
    max_valid_acc_topk = max(valid_acc_topk)
    max_valid_prec_topk = max(valid_prec_topk)
    max_valid_rec_topk = max(valid_rec_topk)
    max_valid_fmeasure_topk = max(valid_fmeasure_topk)
    max_valid_hamming_loss_topk = max(valid_hamming_loss_topk)

    if FLAGS.kfold != -1:
        std_valid_loss = statistics.stdev(valid_loss)
        std_valid_acc_th = statistics.stdev(valid_acc_th) # to change
        std_valid_prec_th = statistics.stdev(valid_prec_th)
        std_valid_rec_th = statistics.stdev(valid_rec_th)
        std_valid_fmeasure_th = statistics.stdev(valid_fmeasure_th)
        std_valid_hamming_loss_th = statistics.stdev(valid_hamming_loss_th)
        std_valid_acc_topk = statistics.stdev(valid_acc_topk)
        std_valid_prec_topk = statistics.stdev(valid_prec_topk)
        std_valid_rec_topk = statistics.stdev(valid_rec_topk)
        std_valid_fmeasure_topk = statistics.stdev(valid_fmeasure_topk)
        std_valid_hamming_loss_topk = statistics.stdev(valid_hamming_loss_topk)
    
    final_valid_loss = sum(valid_loss)/num_runs # final is average
    final_valid_acc_th = sum(valid_acc_th)/num_runs
    final_valid_prec_th = sum(valid_prec_th)/num_runs
    final_valid_rec_th = sum(valid_rec_th)/num_runs
    final_valid_fmeasure_th = sum(valid_fmeasure_th)/num_runs
    final_valid_hamming_loss_th = sum(valid_hamming_loss_th)/num_runs
    final_valid_acc_topk = sum(valid_acc_topk)/num_runs
    final_valid_prec_topk = sum(valid_prec_topk)/num_runs
    final_valid_rec_topk = sum(valid_rec_topk)/num_runs
    final_valid_fmeasure_topk = sum(valid_fmeasure_topk)/num_runs
    final_valid_hamming_loss_topk = sum(valid_hamming_loss_topk)/num_runs
    
    print("Bi-GRU==>Final Validation results Validation Loss:%.3f ± %.3f (%.3f - %.3f)\tValidation Accuracy: %.3f ± %.3f (%.3f - %.3f)\tValidation Hamming Loss: %.3f ± %.3f (%.3f - %.3f)\tValidation Precision: %.3f ± %.3f (%.3f - %.3f)\tValidation Recall: %.3f ± %.3f (%.3f - %.3f)\tValidation F-measure: %.3f ± %.3f (%.3f - %.3f)\tValidation Accuracy@k: %.3f ± %.3f (%.3f - %.3f)\tValidation Hamming Loss@k: %.3f ± %.3f (%.3f - %.3f)\tValidation Precision@k: %.3f ± %.3f (%.3f - %.3f)\tValidation Recall@k: %.3f ± %.3f (%.3f - %.3f)\tValidation F-measure@k: %.3f ± %.3f (%.3f - %.3f)" % (final_valid_loss,std_valid_loss,min_valid_loss,max_valid_loss,final_valid_acc_th,std_valid_acc_th,min_valid_acc_th,max_valid_acc_th,final_valid_hamming_loss_th,std_valid_hamming_loss_th,min_valid_hamming_loss_th,max_valid_hamming_loss_th,final_valid_prec_th,std_valid_prec_th,min_valid_prec_th,max_valid_prec_th,final_valid_rec_th,std_valid_rec_th,min_valid_rec_th,max_valid_rec_th,final_valid_fmeasure_th,std_valid_fmeasure_th,min_valid_fmeasure_th,max_valid_fmeasure_th,final_valid_acc_topk,std_valid_acc_topk,min_valid_acc_topk,max_valid_acc_topk,final_valid_hamming_loss_topk,std_valid_hamming_loss_topk,min_valid_hamming_loss_topk,max_valid_hamming_loss_topk,final_valid_prec_topk,std_valid_prec_topk,min_valid_prec_topk,max_valid_prec_topk,final_valid_rec_topk,std_valid_rec_topk,min_valid_rec_topk,max_valid_rec_topk,final_valid_fmeasure_topk,std_valid_fmeasure_topk,min_valid_fmeasure_topk,max_valid_fmeasure_topk))
    #output the result to a file
    output_valid = output_valid + "\n" + "Bi-GRU==>Final Validation results Validation Loss:%.3f ± %.3f (%.3f - %.3f)\tValidation Accuracy: %.3f ± %.3f (%.3f - %.3f)\tValidation Hamming Loss: %.3f ± %.3f (%.3f - %.3f)\tValidation Precision: %.3f ± %.3f (%.3f - %.3f)\tValidation Recall: %.3f ± %.3f (%.3f - %.3f)\tValidation F-measure: %.3f ± %.3f (%.3f - %.3f)\tValidation Accuracy@k: %.3f ± %.3f (%.3f - %.3f)\tValidation Hamming Loss@k: %.3f ± %.3f (%.3f - %.3f)\tValidation Precision@k: %.3f ± %.3f (%.3f - %.3f)\tValidation Recall@k: %.3f ± %.3f (%.3f - %.3f)\tValidation F-measure@k: %.3f ± %.3f (%.3f - %.3f)" % (final_valid_loss,std_valid_loss,min_valid_loss,max_valid_loss,final_valid_acc_th,std_valid_acc_th,min_valid_acc_th,max_valid_acc_th,final_valid_hamming_loss_th,std_valid_hamming_loss_th,min_valid_hamming_loss_th,max_valid_hamming_loss_th,final_valid_prec_th,std_valid_prec_th,min_valid_prec_th,max_valid_prec_th,final_valid_rec_th,std_valid_rec_th,min_valid_rec_th,max_valid_rec_th,final_valid_fmeasure_th,std_valid_fmeasure_th,min_valid_fmeasure_th,max_valid_fmeasure_th,final_valid_acc_topk,std_valid_acc_topk,min_valid_acc_topk,max_valid_acc_topk,final_valid_hamming_loss_topk,std_valid_hamming_loss_topk,min_valid_hamming_loss_topk,max_valid_hamming_loss_topk,final_valid_prec_topk,std_valid_prec_topk,min_valid_prec_topk,max_valid_prec_topk,final_valid_rec_topk,std_valid_rec_topk,min_valid_rec_topk,max_valid_rec_topk,final_valid_fmeasure_topk,std_valid_fmeasure_topk,min_valid_fmeasure_topk,max_valid_fmeasure_topk) + "\n"
    output_csv_valid = output_csv_valid + "\n" + "average" + "," + str(round(final_valid_loss,3)) + "±" + str(round(std_valid_loss,3)) + "," + str(round(final_valid_hamming_loss_th,3)) + "±" + str(round(std_valid_hamming_loss_th,3)) + "," + str(round(final_valid_acc_th,3)) + "±" + str(round(std_valid_acc_th,3)) + "," + str(round(final_valid_prec_th,3)) + "±" + str(round(std_valid_prec_th,3)) + "," + str(round(final_valid_rec_th,3)) + "±" + str(round(std_valid_rec_th,3)) + "," + str(round(final_valid_fmeasure_th,3)) + "±" + str(round(std_valid_fmeasure_th,3)) + "," + str(round(final_valid_acc_topk,3)) + "±" + str(round(std_valid_acc_topk,3)) + "," + str(round(final_valid_hamming_loss_topk,3)) + "±" + str(round(std_valid_hamming_loss_topk,3)) + "," + str(round(final_valid_prec_topk,3)) + "±" + str(round(std_valid_prec_topk,3)) + "," + str(round(final_valid_rec_topk,3)) + "±" + str(round(std_valid_rec_topk,3)) + "," + str(round(final_valid_fmeasure_topk,3)) + "±" + str(round(std_valid_fmeasure_topk,3))
    
    # 8. report min, max, std, average for the test results
    min_test_loss = min(test_loss)
    min_test_acc_th = min(test_acc_th)
    min_test_prec_th = min(test_prec_th)
    min_test_rec_th = min(test_rec_th)
    min_test_fmeasure_th = min(test_fmeasure_th)
    min_test_hamming_loss_th = min(test_hamming_loss_th)
    min_test_acc_topk = min(test_acc_topk)
    min_test_prec_topk = min(test_prec_topk)
    min_test_rec_topk = min(test_rec_topk)
    min_test_fmeasure_topk = min(test_fmeasure_topk)
    min_test_hamming_loss_topk = min(test_hamming_loss_topk)
    
    max_test_loss = max(test_loss)
    max_test_acc_th = max(test_acc_th)
    max_test_prec_th = max(test_prec_th)
    max_test_rec_th = max(test_rec_th)
    max_test_fmeasure_th = max(test_fmeasure_th)
    max_test_hamming_loss_th = max(test_hamming_loss_th)
    max_test_acc_topk = max(test_acc_topk)
    max_test_prec_topk = max(test_prec_topk)
    max_test_rec_topk = max(test_rec_topk)
    max_test_fmeasure_topk = max(test_fmeasure_topk)
    max_test_hamming_loss_topk = max(test_hamming_loss_topk)
    
    if FLAGS.kfold != -1:
        std_test_loss = statistics.stdev(test_loss)
        std_test_acc_th = statistics.stdev(test_acc_th) # to change
        std_test_prec_th = statistics.stdev(test_prec_th)
        std_test_rec_th = statistics.stdev(test_rec_th)
        std_test_fmeasure_th = statistics.stdev(test_fmeasure_th)
        std_test_hamming_loss_th = statistics.stdev(test_hamming_loss_th)
        std_test_acc_topk = statistics.stdev(test_acc_topk)
        std_test_prec_topk = statistics.stdev(test_prec_topk)
        std_test_rec_topk = statistics.stdev(test_rec_topk)
        std_test_fmeasure_topk = statistics.stdev(test_fmeasure_topk)
        std_test_hamming_loss_topk = statistics.stdev(test_hamming_loss_topk)
        
    final_test_loss = sum(test_loss)/num_runs # final is average
    final_test_acc_th = sum(test_acc_th)/num_runs
    final_test_prec_th = sum(test_prec_th)/num_runs
    final_test_rec_th = sum(test_rec_th)/num_runs
    final_test_fmeasure_th = sum(test_fmeasure_th)/num_runs
    final_test_hamming_loss_th = sum(test_hamming_loss_th)/num_runs
    final_test_acc_topk = sum(test_acc_topk)/num_runs
    final_test_prec_topk = sum(test_prec_topk)/num_runs
    final_test_rec_topk = sum(test_rec_topk)/num_runs
    final_test_fmeasure_topk = sum(test_fmeasure_topk)/num_runs
    final_test_hamming_loss_topk = sum(test_hamming_loss_topk)/num_runs
    
    print("Bi-GRU==>Final Test results Validation Loss:%.3f ± %.3f (%.3f - %.3f)\tValidation Accuracy: %.3f ± %.3f (%.3f - %.3f)\tValidation Hamming Loss: %.3f ± %.3f (%.3f - %.3f)\tValidation Precision: %.3f ± %.3f (%.3f - %.3f)\tValidation Recall: %.3f ± %.3f (%.3f - %.3f)\tValidation F-measure: %.3f ± %.3f (%.3f - %.3f)\tValidation Accuracy@k: %.3f ± %.3f (%.3f - %.3f)\tValidation Hamming Loss@k: %.3f ± %.3f (%.3f - %.3f)\tValidation Precision@k: %.3f ± %.3f (%.3f - %.3f)\tValidation Recall@k: %.3f ± %.3f (%.3f - %.3f)\tValidation F-measure@k: %.3f ± %.3f (%.3f - %.3f)" % (final_test_loss,std_test_loss,min_test_loss,max_test_loss,final_test_acc_th,std_test_acc_th,min_test_acc_th,max_test_acc_th,final_test_hamming_loss_th,std_test_hamming_loss_th,min_test_hamming_loss_th,max_test_hamming_loss_th,final_test_prec_th,std_test_prec_th,min_test_prec_th,max_test_prec_th,final_test_rec_th,std_test_rec_th,min_test_rec_th,max_test_rec_th,final_test_fmeasure_th,std_test_fmeasure_th,min_test_fmeasure_th,max_test_fmeasure_th,final_test_acc_topk,std_test_acc_topk,min_test_acc_topk,max_test_acc_topk,final_test_hamming_loss_topk,std_test_hamming_loss_topk,min_test_hamming_loss_topk,max_test_hamming_loss_topk,final_test_prec_topk,std_test_prec_topk,min_test_prec_topk,max_test_prec_topk,final_test_rec_topk,std_test_rec_topk,min_test_rec_topk,max_test_rec_topk,final_test_fmeasure_topk,std_test_fmeasure_topk,min_test_fmeasure_topk,max_test_fmeasure_topk))
    #output the result to a file
    output_test = output_test + "\n" + "Bi-GRU==>Final Test results Validation Loss:%.3f ± %.3f (%.3f - %.3f)\tValidation Accuracy: %.3f ± %.3f (%.3f - %.3f)\tValidation Hamming Loss: %.3f ± %.3f (%.3f - %.3f)\tValidation Precision: %.3f ± %.3f (%.3f - %.3f)\tValidation Recall: %.3f ± %.3f (%.3f - %.3f)\tValidation F-measure: %.3f ± %.3f (%.3f - %.3f)\tValidation Accuracy@k: %.3f ± %.3f (%.3f - %.3f)\tValidation Hamming Loss@k: %.3f ± %.3f (%.3f - %.3f)\tValidation Precision@k: %.3f ± %.3f (%.3f - %.3f)\tValidation Recall@k: %.3f ± %.3f (%.3f - %.3f)\tValidation F-measure@k: %.3f ± %.3f (%.3f - %.3f)" % (final_test_loss,std_test_loss,min_test_loss,max_test_loss,final_test_acc_th,std_test_acc_th,min_test_acc_th,max_test_acc_th,final_test_hamming_loss_th,std_test_hamming_loss_th,min_test_hamming_loss_th,max_test_hamming_loss_th,final_test_prec_th,std_test_prec_th,min_test_prec_th,max_test_prec_th,final_test_rec_th,std_test_rec_th,min_test_rec_th,max_test_rec_th,final_test_fmeasure_th,std_test_fmeasure_th,min_test_fmeasure_th,max_test_fmeasure_th,final_test_acc_topk,std_test_acc_topk,min_test_acc_topk,max_test_acc_topk,final_test_hamming_loss_topk,std_test_hamming_loss_topk,min_test_hamming_loss_topk,max_test_hamming_loss_topk,final_test_prec_topk,std_test_prec_topk,min_test_prec_topk,max_test_prec_topk,final_test_rec_topk,std_test_rec_topk,min_test_rec_topk,max_test_rec_topk,final_test_fmeasure_topk,std_test_fmeasure_topk,min_test_fmeasure_topk,max_test_fmeasure_topk) + "\n"
    output_csv_test = output_csv_test + "\n" + "average" + "," + str(round(final_test_loss,3)) + "±" + str(round(std_test_loss,3)) + "," + str(round(final_test_hamming_loss_th,3)) + "±" + str(round(std_test_hamming_loss_th,3)) + "," + str(round(final_test_acc_th,3)) + "±" + str(round(std_test_acc_th,3)) + "," + str(round(final_test_prec_th,3)) + "±" + str(round(std_test_prec_th,3)) + "," + str(round(final_test_rec_th,3)) + "±" + str(round(std_test_rec_th,3)) + "," + str(round(final_test_fmeasure_th,3)) + "±" + str(round(std_test_fmeasure_th,3)) + "," + str(round(final_test_acc_topk,3)) + "±" + str(round(std_test_acc_topk,3)) + "," + str(round(final_test_hamming_loss_topk,3)) + "±" + str(round(std_test_hamming_loss_topk,3)) + "," + str(round(final_test_prec_topk,3)) + "±" + str(round(std_test_prec_topk,3)) + "," + str(round(final_test_rec_topk,3)) + "±" + str(round(std_test_rec_topk,3)) + "," + str(round(final_test_fmeasure_topk,3)) + "±" + str(round(std_test_fmeasure_topk,3))
    
    # get the experimental input settings
    #setting_dict = tf.flags.FLAGS.__flags
    #setting = ""
    #for key, value in setting_dict.items():
    #    setting = setting + key + ": " + str(value) + '\n'
    #setting:batch_size,embed_size,label_sim_threshold,lambda_sim,weight_decay_testing
    setting = "batch_size: " + str(FLAGS.batch_size) + "\nembed_size: " + str(FLAGS.embed_size) + "\nvalidate_step: " + str(FLAGS.validate_step) + "\nlabel_sim_threshold: " + str(FLAGS.label_sim_threshold) + "\nlambda_sim: " + str(FLAGS.lambda_sim) + "\nlambda_sub: " + str(FLAGS.lambda_sub) + "\nnum_epochs: " + str(FLAGS.num_epochs) + "\nkeep_label_percent: " + str(FLAGS.keep_label_percent) + "\nweight_decay_testing: " + str(FLAGS.weight_decay_testing) + "\nearly_stop_lr: " + str(FLAGS.early_stop_lr) + "\ndynamic_sem: " + str(FLAGS.dynamic_sem) + "\ndynamic_sem_l2: " + str(FLAGS.dynamic_sem_l2)
    print("--- The whole program took %s seconds ---" % (time.time() - start_time))
    time_used = "--- The whole program took %s seconds ---" % (time.time() - start_time)
    if FLAGS.kfold != -1:
        print("--- The average training took %s ± %s seconds ---" % (sum(time_train)/num_runs,statistics.stdev(time_train)))
        average_time_train = "--- The average training took %s ± %s seconds ---" % (sum(time_train)/num_runs,statistics.stdev(time_train))
    else:
        print("--- The average training took %s ± %s seconds ---" % (sum(time_train)/num_runs,0))
        average_time_train = "--- The average training took %s ± %s seconds ---" % (sum(time_train)/num_runs,0)

    # output setting configuration, results, prediction and time used
    output_to_file('l2 ' + str(FLAGS.lambda_sim) + " l3 " + str(FLAGS.lambda_sub) + ' th' + str(FLAGS.label_sim_threshold) + ' keep_label_percent' + str(FLAGS.keep_label_percent) + ' kfold' + str(FLAGS.kfold) + ' b_s' + str(FLAGS.batch_size) + ' gp_id' + str(FLAGS.marking_id) + '.txt',setting + '\n' + output_valid + '\n' + output_test + '\n' + prediction_str + '\n' + time_used + '\n' + average_time_train)
    # output structured evaluation results
    output_to_file('l2 ' + str(FLAGS.lambda_sim) + " l3 " + str(FLAGS.lambda_sub) + ' th' + str(FLAGS.label_sim_threshold) + ' keep_label_percent' + str(FLAGS.keep_label_percent) + ' kfold' + str(FLAGS.kfold) + ' b_s' + str(FLAGS.batch_size) + ' gp_id' + str(FLAGS.marking_id) + ' valid.csv',output_csv_valid)
    output_to_file('l2 ' + str(FLAGS.lambda_sim) + " l3 " + str(FLAGS.lambda_sub) + ' th' + str(FLAGS.label_sim_threshold) + ' keep_label_percent' + str(FLAGS.keep_label_percent) + ' kfold' + str(FLAGS.kfold) + ' b_s' + str(FLAGS.batch_size) + ' gp_id' + str(FLAGS.marking_id) + ' test.csv',output_csv_test)
    pass

def output_to_file(file_name,str):
    with open(file_name, 'w', encoding="utf-8-sig") as f_output:
        f_output.write(str + '\n')
    
def assign_pretrained_word_embedding(sess,vocabulary_index2word,vocab_size,model,num_run,word2vec_model_path=None):
    if num_run==0:
        print("using pre-trained word emebedding.started.word2vec_model_path:",word2vec_model_path)
    # transform embedding input into a dictionary
    # word2vecc=word2vec.load('word_embedding.txt') #load vocab-vector fiel.word2vecc['w91874']
    word2vec_model = word2vec.load(word2vec_model_path, kind='bin')
    word2vec_dict = {}
    for word, vector in zip(word2vec_model.vocab, word2vec_model.vectors):
        word2vec_dict[word] = vector
    word_embedding_2dlist = [[]] * vocab_size  # create an empty word_embedding list: which is a list of list, i.e. a list of word, where each word is a list of values as an embedding vector.
    word_embedding_2dlist[0] = np.zeros(FLAGS.embed_size)  # assign empty for first word:'PAD'
    bound = np.sqrt(6.0) / np.sqrt(vocab_size)  # bound for random variables.
    count_exist = 0;
    count_not_exist = 0
    for i in range(1, vocab_size):  # loop each word
        word = vocabulary_index2word[i]  # get a word
        embedding = None
        try:
            embedding = word2vec_dict[word]  # try to get vector:it is an array.
        except Exception:
            embedding = None
        if embedding is not None:  # the 'word' exist a embedding
            word_embedding_2dlist[i] = embedding;
            count_exist = count_exist + 1  # assign array to this word.
        else:  # no embedding for this word
            word_embedding_2dlist[i] = np.random.uniform(-bound, bound, FLAGS.embed_size);
            count_not_exist = count_not_exist + 1  # init a random value for the word.
    word_embedding_final = np.array(word_embedding_2dlist)  # covert to 2d array.
    #print(word_embedding_final[0]) # print the original embedding for the first word
    word_embedding = tf.constant(word_embedding_final, dtype=tf.float32)  # convert to tensor
    t_assign_embedding = tf.assign(model.Embedding,word_embedding)  # assign this value to our embedding variables of our model.
    sess.run(t_assign_embedding);
    if num_run==0:
        print("word. exists embedding:", count_exist, " ;word not exist embedding:", count_not_exist)
        print("using pre-trained word emebedding.ended...")

def assign_sim_sub_matrices(sess,lambda_sim,lambda_sub,label_sim_mat,label_sub_mat,model):
    if lambda_sim != 0:
        label_sim_mat_tf = tf.constant(label_sim_mat, dtype=tf.float32)  # convert to tensor
        t_assign_sim = tf.assign(model.label_sim_matrix,label_sim_mat_tf)  # assign this value to our embedding variables of our model.
        sess.run(t_assign_sim)
    if lambda_sub != 0:
        label_sub_mat_tf = tf.constant(label_sub_mat, dtype=tf.float32)  # convert to tensor
        t_assign_sub = tf.assign(model.label_sub_matrix,label_sub_mat_tf)
        sess.run(t_assign_sub)
        
# based on a threshold, 在验证集上做验证，报告损失、精确度-multilabel
def do_eval_multilabel_threshold(sess,modelToEval,label_sim_mat,label_sub_mat,evalX,evalY,batch_size,vocabulary_index2word,vocabulary_index2word_label,epoch,threshold=0.5,display_results_bool=True,hamming_q=FLAGS.ave_labels_per_doc,top_number=FLAGS.topk,record_to_tensorboard=True):
    #print(display_results_bool)
    #print("hi i am evaluating man")
    number_examples=len(evalX)
    print("number_examples", number_examples)
    #generate random index for batch and document
    #rn.seed(1)
    batch_chosen=rn.randint(0,number_examples//batch_size)
    x_chosen=rn.randint(0,batch_size)
    eval_loss,eval_acc_th,eval_prec_th,eval_rec_th,eval_fmeasure_th,eval_acc_topk,eval_prec_topk,eval_rec_topk,eval_fmeasure_topk,eval_hamming_loss_th,eval_hamming_loss_topk,eval_counter=0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0
    eval_step=epoch*(number_examples//batch_size)
    for start,end in zip(range(0,number_examples,batch_size),range(batch_size,number_examples,batch_size)):
        feed_dict = {modelToEval.input_x: evalX[start:end], modelToEval.dropout_keep_prob: 1, modelToEval.label_sim_matrix:label_sim_mat, modelToEval.label_sub_matrix:label_sub_mat}
        #if (start==0):
        #    print(evalX[start:end])
        if not FLAGS.multi_label_flag:
            feed_dict[modelToEval.input_y] = evalY[start:end]
        else:
            feed_dict[modelToEval.input_y_multilabel] = evalY[start:end]
        #curr_eval_loss, logits,curr_eval_acc= sess.run([modelToEval.loss_val,modelToEval.logits,modelToEval.accuracy],feed_dict)#curr_eval_acc--->modelToEval.accuracy
        curr_summary_str,curr_summary_l_epoch,curr_eval_loss,logits= sess.run([modelToEval.validation_loss,modelToEval.validation_loss_per_epoch,modelToEval.loss_val,modelToEval.logits],feed_dict)#curr_eval_acc--->modelToEval.accuracy
        if record_to_tensorboard:
            eval_step = eval_step + 1
            modelToEval.writer.add_summary(curr_summary_str,eval_step)
            if eval_counter==0:
                modelToEval.writer.add_summary(curr_summary_l_epoch,epoch)
        eval_counter=eval_counter+1
        #print(type(logits))
        #n=0
        #print(len(logits)) #=batch_size
        curr_eval_acc_th=0.0
        curr_eval_prec_th=0.0
        curr_eval_rec_th=0.0
        curr_hamming_loss_th=0.0
        curr_eval_acc_topk=0.0
        curr_eval_prec_topk=0.0
        curr_eval_rec_topk=0.0
        curr_hamming_loss_topk=0.0
        for x in range(0,len(logits)):
            label_list_th = get_label_using_logits_threshold(logits[x],threshold)
            label_list_topk = get_label_using_logits(logits[x], vocabulary_index2word_label,top_number)
            # display a particular prediction result
            if x==x_chosen and start==batch_chosen*batch_size and display_results_bool==True:
                print('doc:',*display_results(evalX[start+x],vocabulary_index2word))
                print('prediction-0.5:',*display_results(label_list_th,vocabulary_index2word_label))
                print('prediction-topk:',*display_results(label_list_topk,vocabulary_index2word_label))
                get_indexes = lambda x, xs: [i for (y, i) in zip(xs, range(len(xs))) if x == y]
                print('labels:',*display_results(get_indexes(1,evalY[start+x]),vocabulary_index2word_label))
            #print(label_list_top5)
            #print(evalY[start:end][x])
            curr_eval_acc_th=curr_eval_acc_th + calculate_accuracy(list(label_list_th), evalY[start:end][x],eval_counter)
            precision, recall = calculate_precision_recall(list(label_list_th), evalY[start:end][x],eval_counter)
            curr_eval_prec_th = curr_eval_prec_th + precision
            curr_eval_rec_th = curr_eval_rec_th + recall
            hamming_loss_th = calculate_hamming_loss(list(label_list_th), evalY[start:end][x])
            curr_hamming_loss_th = curr_hamming_loss_th + hamming_loss_th
            
            curr_eval_acc_topk=curr_eval_acc_topk + calculate_accuracy(list(label_list_topk), evalY[start:end][x],eval_counter)
            precision_topk, recall_topk = calculate_precision_recall(list(label_list_topk), evalY[start:end][x],eval_counter)
            curr_eval_prec_topk = curr_eval_prec_topk + precision_topk
            curr_eval_rec_topk = curr_eval_rec_topk + recall_topk
            hamming_loss_topk = calculate_hamming_loss(list(label_list_topk), evalY[start:end][x])
            curr_hamming_loss_topk = curr_hamming_loss_topk + hamming_loss_topk

            #print(curr_eval_acc)
        eval_acc_th = eval_acc_th + curr_eval_acc_th/float(len(logits))
        eval_prec_th = eval_prec_th + curr_eval_prec_th/float(len(logits))
        eval_rec_th = eval_rec_th + curr_eval_rec_th/float(len(logits))
        eval_hamming_loss_th = eval_hamming_loss_th + curr_hamming_loss_th/float(len(logits))
        
        eval_acc_topk = eval_acc_topk + curr_eval_acc_topk/float(len(logits))
        eval_prec_topk = eval_prec_topk + curr_eval_prec_topk/float(len(logits))
        eval_rec_topk = eval_rec_topk + curr_eval_rec_topk/float(len(logits))
        eval_hamming_loss_topk = eval_hamming_loss_topk + curr_hamming_loss_topk/float(len(logits))
        #print("eval_acc", eval_acc)
        eval_loss=eval_loss+curr_eval_loss
        #eval_counter=eval_counter+1
        #print("eval_counter", eval_counter)
    eval_prec_th = eval_prec_th/float(eval_counter)
    eval_rec_th = eval_rec_th/float(eval_counter)
    eval_hamming_loss_th = eval_hamming_loss_th/float(eval_counter)
    if (eval_prec_th+eval_rec_th)>0:
        eval_fmeasure_th = 2*eval_prec_th*eval_rec_th/(eval_prec_th+eval_rec_th)
    
    eval_prec_topk = eval_prec_topk/float(eval_counter)
    eval_rec_topk = eval_rec_topk/float(eval_counter)
    eval_hamming_loss_topk = eval_hamming_loss_topk/float(eval_counter)
    if (eval_prec_topk+eval_rec_topk)>0:
        eval_fmeasure_topk = 2*eval_prec_topk*eval_rec_topk/(eval_prec_topk+eval_rec_topk)    
    return eval_loss/float(eval_counter),eval_acc_th/float(eval_counter),eval_prec_th,eval_rec_th,eval_fmeasure_th,eval_hamming_loss_th/hamming_q,eval_acc_topk/float(eval_counter),eval_prec_topk,eval_rec_topk,eval_fmeasure_topk,eval_hamming_loss_topk/hamming_q

def display_for_qualitative_evaluation(sess,modelToEval,label_sim_mat,label_sub_mat,evalX,evalY,batch_size,vocabulary_index2word,vocabulary_index2word_label,threshold=0.5):
    prediction_str=""
    number_examples=len(evalX)
    rn_dict={}
    rn.seed(1) # set the seed to produce same documents for prediction
    for i in range(0,500):
        batch_chosen=rn.randint(0,number_examples//batch_size)
        x_chosen=rn.randint(0,batch_size)
        rn_dict[(batch_chosen*batch_size,x_chosen)]=1
    for start,end in zip(range(0,number_examples,batch_size),range(batch_size,number_examples,batch_size)):
        feed_dict = {modelToEval.input_x: evalX[start:end], modelToEval.dropout_keep_prob: 1, modelToEval.label_sim_matrix:label_sim_mat, modelToEval.label_sub_matrix:label_sub_mat}
        #if (start==0):
        #    print(evalX[start:end])
        if not FLAGS.multi_label_flag:
            feed_dict[modelToEval.input_y] = evalY[start:end]
        else:
            feed_dict[modelToEval.input_y_multilabel] = evalY[start:end]
        #curr_eval_loss, logits,curr_eval_acc= sess.run([modelToEval.loss_val,modelToEval.logits,modelToEval.accuracy],feed_dict)#curr_eval_acc--->modelToEval.accuracy
        curr_eval_loss,logits= sess.run([modelToEval.loss_val,modelToEval.logits],feed_dict)#curr_eval_acc--->modelToEval.accuracy
        for x in range(0,len(logits)):
            label_list_th = get_label_using_logits_threshold(logits[x],threshold)
            #label_list_topk = get_label_using_logits(logits[x], vocabulary_index2word_label,top_number=11)
            # display a particular prediction result
            #if x==x_chosen and start==batch_chosen*batch_size:
            if rn_dict.get((start,x)) == 1:
                # print('doc:',*display_results(evalX[start+x],vocabulary_index2word))
                # print('prediction-0.5:',*display_results(label_list_th,vocabulary_index2word_label))
                # #print('prediction-topk:',*display_results(label_list_topk,vocabulary_index2word_label))
                # get_indexes = lambda x, xs: [i for (y, i) in zip(xs, range(len(xs))) if x == y]
                # print('labels:',*display_results(get_indexes(1,evalY[start+x]),vocabulary_index2word_label))
                doc = 'doc: ' + ' '.join(display_results(evalX[start+x],vocabulary_index2word))
                pred = 'prediction-0.5: ' + ' '.join(display_results(label_list_th,vocabulary_index2word_label))
                #print('prediction-topk:',*display_results(label_list_topk,vocabulary_index2word_label))
                get_indexes = lambda x, xs: [i for (y, i) in zip(xs, range(len(xs))) if x == y]
                label = 'labels: ' + ' '.join(display_results(get_indexes(1,evalY[start+x]),vocabulary_index2word_label))
                prediction_str = prediction_str + '\n' + doc + '\n' + pred + '\n' + label + '\n'
                #print(prediction_str)
    return prediction_str
    
#从logits中取出前五 get label using logits
def get_label_using_logits(logits,vocabulary_index2word_label,top_number=1):
    #print("get_label_using_logits.logits:",logits) #1-d array: array([-5.69036102, -8.54903221, -5.63954401, ..., -5.83969498,-5.84496021, -6.13911009], dtype=float32))
    index_list=np.argsort(logits)[-top_number:]
    index_list=index_list[::-1]
    #label_list=[]
    #for index in index_list:
    #    label=vocabulary_index2word_label[index]
    #    label_list.append(label) #('get_label_using_logits.label_list:', [u'-3423450385060590478', u'2838091149470021485', u'-3174907002942471215', u'-1812694399780494968', u'6815248286057533876'])
    return index_list

#从sigmoid(logits)中取出大于0.5的
def get_label_using_logits_threshold(logits,threshold=0.5):
    sig = sigmoid_array(logits)
    index_list = np.where(sig > threshold)[0]
    return index_list

def display_results(index_list,vocabulary_index2word_label):
    label_list=[]
    for index in index_list:
        if index!=0:
            label=vocabulary_index2word_label[index]
            label_list.append(label)
    return label_list

def sigmoid_array(x):
    return 1 / (1 + np.exp(-x))

#统计预测的准确率
def calculate_accuracy(labels_predicted,labels,eval_counter): # this should be same as the recall value
    # turn the multihot representation to a list of true labels
    label_nozero=[]
    #print("labels:",labels)
    labels=list(labels)
    for index,label in enumerate(labels):
        if label>0:
            label_nozero.append(index)
    #if eval_counter<2:
        #print("labels_predicted:",labels_predicted," ;labels_nozero:",label_nozero)
    overlapping = 0
    label_dict = {x: x for x in label_nozero} # create a dictionary of labels for the true labels
    union = len(label_dict)
    for label_predict in labels_predicted:
        flag = label_dict.get(label_predict, None)
        if flag is not None:
            overlapping = overlapping + 1
        else:
            union = union + 1        
    return overlapping / union

def calculate_precision_recall(labels_predicted, labels,eval_counter):
    label_nozero=[]
    #print("labels:",labels)
    labels=list(labels)
    for index,label in enumerate(labels):
        if label>0:
            label_nozero.append(index)
    #if eval_counter<2:
    #    print("labels_predicted:",labels_predicted," ;labels_nozero:",label_nozero)
    count = 0
    label_dict = {x: x for x in label_nozero}
    for label_predict in labels_predicted:
        flag = label_dict.get(label_predict, None)
        if flag is not None:
            count = count + 1
    if (len(labels_predicted)==0): # if nothing predicted, then set the precision as 0.
        precision=0
    else: 
        precision = count / len(labels_predicted)
    recall = count / len(label_nozero)
    #fmeasure = 2*precision*recall/(precision+recall)
    #print(count, len(label_nozero))
    return precision, recall
   
# calculate the symmetric_difference
def calculate_hamming_loss(labels_predicted, labels):
    label_nozero=[]
    #print("labels:",labels)
    labels=list(labels)
    for index,label in enumerate(labels):
        if label>0:
            label_nozero.append(index)
    count = 0
    label_dict = {x: x for x in label_nozero} # get the true labels

    for label_predict in labels_predicted:
        flag = label_dict.get(label_predict, None)
        if flag is not None:
            count = count + 1 # get the number of overlapping labels
    
    return len(label_dict)+len(labels_predicted)-2*count
    
if __name__ == "__main__":
    tf.app.run()
