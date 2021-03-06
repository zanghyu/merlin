import os, sys
import random
import numpy as np

from io_funcs.binary_io import BinaryIOCollection

from keras_lib.model import kerasModels
from keras_lib import data_utils

class TrainKerasModels(kerasModels):
    
    def __init__(self, n_in, hidden_layer_size, n_out, hidden_layer_type, output_type='linear', dropout_rate=0.0, loss_function='mse', optimizer='adam'):
        
        kerasModels.__init__(self, n_in, hidden_layer_size, n_out, hidden_layer_type, output_type, dropout_rate, loss_function, optimizer)
        
        #### TODO: Find a good way to pass below params ####
        self.merge_size  = 4400
        self.seq_length  = 200 
        self.bucket_range = 100
       
        self.stateful = False
       
        pass;
    
    def train_feedforward_model(self, train_x, train_y, batch_size=256, num_of_epochs=10, shuffle_data=True): 
        self.model.fit(train_x, train_y, batch_size=batch_size, epochs=num_of_epochs, shuffle=shuffle_data)
    
    def train_sequence_model(self, train_x, train_y, train_flen, batch_size=1, num_of_epochs=10, shuffle_data=True, training_algo=1):
        if batch_size == 1: 
            self.train_recurrent_model_batchsize_one(train_x, train_y, num_of_epochs, shuffle_data, training_algo)
        else:
            self.train_recurrent_model(train_x, train_y, train_flen, batch_size, num_of_epochs, shuffle_data, training_algo)

    def train_recurrent_model_batchsize_one(self, train_x, train_y, num_of_epochs, shuffle_data, training_algo):
        ### if batch size is equal to 1 ###
        if training_algo == 1:
            self.train_batchsize_one_model(train_x, train_y, num_of_epochs, shuffle_data)
        elif training_algo == 2:
            new_train_x, new_train_y = data_utils.merge_data(train_x, train_y, self.merge_size)    
            self.train_batchsize_one_model(new_train_x, new_train_y, num_of_epochs, shuffle_data)
        
    def train_batchsize_one_model(self, train_x, train_y, num_of_epochs=10, shuffle_data=True):
        ### train each sentence as a batch ###
        train_idx_list = train_x.keys()
        if shuffle_data:
            random.seed(271638)
            random.shuffle(train_idx_list)        
        
        train_file_number = len(train_idx_list)
        for epoch_num in xrange(num_of_epochs):
            print 'Epoch: %d/%d ' %(epoch_num+1, num_of_epochs)
            file_num = 0
            for file_name in train_idx_list:
                temp_train_x = train_x[file_name]
                temp_train_y = train_y[file_name]
                temp_train_x = np.reshape(temp_train_x, (1, temp_train_x.shape[0], self.n_in))
                temp_train_y = np.reshape(temp_train_y, (1, temp_train_y.shape[0], self.n_out))
                self.model.train_on_batch(temp_train_x, temp_train_y)
                #self.model.fit(temp_train_x, temp_train_y, epochs=1, shuffle=False, verbose=0)
                file_num += 1
                data_utils.drawProgressBar(file_num, train_file_number)

            sys.stdout.write("\n")
            
    def train_recurrent_model(self, train_x, train_y, train_flen, batch_size, num_of_epochs, shuffle_data, training_algo):
        ### if batch size more than 1 ###
        if training_algo == 1:
            self.train_truncated_model(train_x, train_y, batch_size, num_of_epochs, shuffle_data)
        elif training_algo == 2:
            self.train_bucket_model_with_padding(train_x, train_y, train_flen, batch_size, num_of_epochs, shuffle_data)
        elif training_algo == 3:
            self.train_bucket_model_without_padding(train_x, train_y, train_flen, batch_size, num_of_epochs, shuffle_data)
        else:
            print "Chose training algo. for batch size more than 1:"
            print "1) Truncated Model"
            print "2) bucket Model (with padding)"
            print "3) bucket Model (without padding)"
            sys.exit(0)

    def train_truncated_model(self, train_x, train_y, batch_size, num_of_epochs, shuffle_data):
        ### Method 1 ###
        temp_train_x = data_utils.transform_data_to_3d_matrix(train_x, seq_length=self.seq_length, merge_size=self.merge_size, shuffle_data=shuffle_data)
        print("Input shape: "+str(temp_train_x.shape))
         
        temp_train_y = data_utils.transform_data_to_3d_matrix(train_y, seq_length=self.seq_length, merge_size=self.merge_size, shuffle_data=shuffle_data) 
        print("Output shape: "+str(temp_train_y.shape))
               
        if self.stateful:
            temp_train_x, temp_train_y = get_stateful_data(temp_train_x, temp_train_y, batch_size)
                    
        self.model.fit(temp_train_x, temp_train_y, batch_size=batch_size, epochs=num_of_epochs, shuffle=False, verbose=1)
    
    def train_bucket_model_with_padding(self, train_x, train_y, train_flen, batch_size, num_of_epochs, shuffle_data):
        ### Method 3 ###
        train_fnum_list  = np.array(train_flen['framenum2utt'].keys())
        train_range_list = range(min(train_fnum_list), max(train_fnum_list), self.bucket_range)
        if shuffle_data:
            random.seed(271638)
            random.shuffle(train_range_list)
        
        train_file_number = len(train_x)
        for epoch_num in xrange(num_of_epochs):
            print 'Epoch: %d/%d ' %(epoch_num+1, num_of_epochs)
            file_num = 0
            for frame_num in train_range_list:
                min_seq_length = frame_num
                max_seq_length = frame_num+self.bucket_range
                sub_train_list  = train_fnum_list[(train_fnum_list>min_seq_length) & (train_fnum_list<=max_seq_length)]
                if len(sub_train_list)==0:
                    continue;
                train_idx_list  = sum([train_flen['framenum2utt'][framenum] for framenum in sub_train_list], [])
                sub_train_x     = dict((filename, train_x[filename]) for filename in train_idx_list)
                sub_train_y     = dict((filename, train_y[filename]) for filename in train_idx_list)
                temp_train_x    = data_utils.transform_data_to_3d_matrix(sub_train_x, max_length=max_seq_length)
                temp_train_y    = data_utils.transform_data_to_3d_matrix(sub_train_y, max_length=max_seq_length) 
                self.model.fit(temp_train_x, temp_train_y, batch_size=batch_size, epochs=1, verbose=0)

                file_num += len(train_idx_list)
                data_utils.drawProgressBar(file_num, train_file_number)

            sys.stdout.write("\n")

    def train_bucket_model_without_padding(self, train_x, train_y, train_flen, batch_size, num_of_epochs, shuffle_data):
        ### Method 4 ###
        train_count_list = train_flen['framenum2utt'].keys()
        if shuffle_data:
            random.seed(271638)
            random.shuffle(train_count_list)
        
        train_file_number = len(train_x)
        for epoch_num in xrange(num_of_epochs):
            print 'Epoch: %d/%d ' %(epoch_num+1, num_of_epochs)
            file_num = 0
            for sequence_length in train_count_list:
                train_idx_list = train_flen['framenum2utt'][sequence_length]
                sub_train_x    = dict((filename, train_x[filename]) for filename in train_idx_list)
                sub_train_y    = dict((filename, train_y[filename]) for filename in train_idx_list)
                temp_train_x   = data_utils.transform_data_to_3d_matrix(sub_train_x, max_length=sequence_length)
                temp_train_y   = data_utils.transform_data_to_3d_matrix(sub_train_y, max_length=sequence_length) 
                self.model.fit(temp_train_x, temp_train_y, batch_size=batch_size, epochs=1, verbose=0)
                
                file_num += len(train_idx_list)
                data_utils.drawProgressBar(file_num, train_file_number)

            sys.stdout.write("\n")

    def predict(self, test_x, out_scaler, gen_test_file_list, sequential_training=False, stateful=False):
        #### compute predictions ####
        io_funcs = BinaryIOCollection()

        test_id_list = test_x.keys()
        test_id_list.sort()

        test_file_number = len(test_id_list) 
        print "generating acoustic features on held-out test data..."
        for utt_index in xrange(test_file_number):
            gen_test_file_name = gen_test_file_list[utt_index]
            temp_test_x        = test_x[test_id_list[utt_index]]
            num_of_rows        = temp_test_x.shape[0]
          
            if stateful:
                temp_test_x = data_utils.get_stateful_input(temp_test_x, self.seq_length, self.batch_size) 
            elif sequential_training:
                temp_test_x = np.reshape(temp_test_x, (1, num_of_rows, self.n_in))
                
            predictions = self.model.predict(temp_test_x)
            if sequential_training:
                predictions = np.reshape(predictions, (num_of_rows, self.n_out))

            data_utils.denorm_data(predictions, out_scaler)
            
            io_funcs.array_to_binary_file(predictions, gen_test_file_name)
            data_utils.drawProgressBar(utt_index+1, test_file_number)

        sys.stdout.write("\n")
       
    def synth_wav(self, bin_file, gen_test_file_list, gen_wav_file_list):
        #### synthesize audio files ####
        test_file_number = len(gen_test_file_list) 
        for utt_index in xrange(test_file_number):
            gen_feat_file = gen_test_file_list[utt_index]
            gen_wav_file  = gen_wav_file_list[utt_index]
            cmd = "%s %s %s" %(bin_file, gen_feat_file, gen_wav_file)
            os.system(cmd)
            data_utils.drawProgressBar(utt_index+1, test_file_number)

        sys.stdout.write("\n")        
