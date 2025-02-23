from fedml import BaseLearner
import keras
from keras.utils import to_categorical
from keras.preprocessing.image import ImageDataGenerator
from keras.models import Sequential
from keras.layers import Dense, Dropout, Activation, Flatten, BatchNormalization
from keras.layers import Conv2D, MaxPooling2D
import numpy as np
import psutil

num_classes = 15

def create_graph(optimizer, learning_rate=0.001, decay=0):
    model = Sequential()
    model.add(Conv2D(32, (3, 3), padding='same',
                     input_shape=[100, 100, 4]))
    model.add(Activation('relu'))
    model.add(Conv2D(32, (3, 3)))
    model.add(Activation('relu'))
    model.add(MaxPooling2D(pool_size=(2, 2)))
    model.add(Dropout(0.25))

    model.add(Conv2D(64, (3, 3), padding='same'))
    model.add(Activation('relu'))
    model.add(Conv2D(64, (3, 3)))
    model.add(Activation('relu'))
    model.add(MaxPooling2D(pool_size=(2, 2)))
    model.add(Dropout(0.25))

    model.add(Flatten())
    model.add(Dense(512))
    model.add(BatchNormalization())
    model.add(Activation('relu'))
    model.add(Dropout(0.5))
    model.add(Dense(num_classes))
    model.add(Activation('softmax'))

    opt = optimizer(learning_rate=learning_rate, decay=decay)
    # Let's train the model using optimizer
    model.compile(loss='categorical_crossentropy',
                  optimizer=opt,
                  metrics=['accuracy'])
    return model


class KerasSequentialAML(BaseLearner):
    """  Keras Sequential base learner."""

    def __init__(self,parameters=None):
        if not "optimizer" in parameters:
            parameters["optimizer"] = keras.optimizers.Adam
        if not "learning_rate" in parameters:
            parameters["learning_rate"] = 0.001
        if not "optimizer" in parameters:
            parameters["decay"] = 0
        self.model = create_graph(parameters["optimizer"], parameters["learning_rate"], parameters["decay"])
        self.datagen = None


    @staticmethod
    def average_weights(weights,parameters):
        """ fdfdsfs """
        if not "model_size" in parameters:
            parameters["model_size"] = None
        #weights = [model.model.get_weights() for model in models]
        avg_w = []
        if parameters["model_size"] is not None:
            data_points = np.sum(np.array(parameters["model_size"]))
        for l in range(len(weights[0])):
            lay_l = np.array([w[l] for w in weights])
            if parameters["model_size"] is not None:
                weight_l_avg = np.sum((lay_l.T*parameters["model_size"]/data_points).T,0 )
            else:
                weight_l_avg = np.mean(lay_l,0)
            avg_w.append(weight_l_avg)
        return avg_w

    def set_weights(self,weights):
        self.model.set_weights(weights)

    def predict(self, x):

        return to_categorical(self.model.predict_classes(x), num_classes=num_classes)
        # return self.model.predict(x)

    def partial_fit(self, x, y, data_order, classes=None, data_set_index=0, parameters=None):  # training_steps=None,
                    # data_augmentation=True,batch_size=32):
        """ Do a partial fit. """
        epochs = 1

        if not "batch_size" in parameters:
            parameters["batch_size"] = 32
        if not "training_steps" in parameters:
            parameters["training_steps"] = None
        if not "data_augmentation" in parameters:
            parameters["data_augmentation"] = True

        if parameters["batch_size"] == "inf":
            parameters["batch_size"] = x.shape[0]

        if parameters["training_steps"] is not None:
            print("training steps is not None: training steps: ", parameters["training_steps"])
            epochs = 1
            start_ind = data_set_index
            end_ind = start_ind + parameters["batch_size"] * parameters["training_steps"]
            ind = []
            while end_ind > x.shape[0]:
                end_ind = end_ind - x.shape[0]
                ind += list(data_order[np.arange(start_ind, x.shape[0])])
                start_ind = 0
                data_order = np.random.permutation(x.shape[0])

            ind += list(data_order[np.arange(start_ind,end_ind)])
            data_set_index = end_ind
            shuffle = True

        else:
            print("training steps: ", parameters["training_steps"])
            ind = np.arange(x.shape[0])
            shuffle = True

        if not parameters["data_augmentation"]:
            print('Not using data augmentation. ')
            self.model.fit(x[ind], y[ind],
                      batch_size=parameters["batch_size"],
                      epochs=epochs,
                      shuffle=shuffle)
        else:
            # print('Using real-time data augmentation.')
            # print("before training(inside partial fit) -- virtual memory used: ", psutil.virtual_memory()[2], "%")

            # This will do preprocessing and realtime data augmentation:
            if self.datagen is None:
                self.datagen = ImageDataGenerator(
                    featurewise_center=False,  # set input mean to 0 over the dataset
                    samplewise_center=False,  # set each sample mean to 0
                    featurewise_std_normalization=False,  # divide inputs by std of the dataset
                    samplewise_std_normalization=False,  # divide each input by its std
                    zca_whitening=False,  # apply ZCA whitening
                    zca_epsilon=1e-06,  # epsilon for ZCA whitening
                    rotation_range=180,  #[M] randomly rotate images in the range (degrees, 0 to 180)
                    # randomly shift images horizontally (fraction of total width)
                    width_shift_range=0.1,
                    # randomly shift images vertically (fraction of total height)
                    height_shift_range=0.1,
                    shear_range=0.,  # set range for random shear
                    zoom_range=0.,  # set range for random zoom
                    channel_shift_range=0.,  # set range for random channel shifts
                    # set mode for filling points outside the input boundaries
                    fill_mode='nearest',
                    cval=0.,  # value used for fill_mode = "constant"
                    horizontal_flip=True,  # randomly flip images
                    vertical_flip=True,  #[M] randomly flip images
                    # set rescaling factor (applied before any other transformation)
                    rescale=None,
                    # set function that will be applied on each input
                    preprocessing_function=None,
                    # image data format, either "channels_first" or "channels_last"
                    data_format=None,
                    validation_split=0.1)

                # Compute quantities required for feature-wise normalization
                # (std, mean, and principal components if ZCA whitening is applied).
                self.datagen.fit(x)

            # Fit the model on the batches generated by datagen.flow().
            self.model.fit_generator(self.datagen.flow(x[ind], y[ind], batch_size=parameters["batch_size"]),
                                     epochs=epochs,
                                     workers=4,
                                     shuffle=shuffle)
            return data_set_index, data_order


