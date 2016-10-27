import tensorflow as tf
import numpy as np
import time
from sklearn.metrics import classification_report


LOSS_TRACE_TAG = "Loss"
SPEED_TRACE_TAG = "Speed"
ACCURACY_TRACE_TAG = "Accuracy"

# todo: hooks should also have prefixes so that one can use the same hook with different parameters
class Hook(object):
    def __init__(self):
        raise NotImplementedError

    def __call__(self, sess, epoch, model, loss):
        raise NotImplementedError


class TraceHook(object):
    def __init__(self, summary_writer=None):
        self.summary_writer = summary_writer

    def __call__(self, sess, epoch, model, loss):
        raise NotImplementedError

    def update_summary(self, sess, current_step, title, value):
        if self.summary_writer is not None:
            cur_summary = tf.scalar_summary(title, value)
            # if you are using some summaries, merge them
            merged_summary_op = tf.merge_summary([cur_summary])
            summary_str = sess.run(merged_summary_op)
            self.summary_writer.add_summary(summary_str, current_step)


class LossHook(TraceHook):
    def __init__(self, iter_interval, batch_size, summary_writer=None):
        super(LossHook, self).__init__(summary_writer)
        self.iter_interval = iter_interval
        self.acc_loss = 0
        self.batch_size = batch_size
        self.iter = 0

    def __call__(self, sess, epoch, model, loss):
        self.iter += 1
        self.acc_loss += loss / self.batch_size
        if not self.iter == 0 and self.iter % self.iter_interval == 0:
            loss = self.acc_loss / self.iter_interval
            print("Epoch " + str(epoch) +
                  "\tIter " + str(self.iter) +
                  "\tLoss " + str(loss))
            self.update_summary(sess, self.iter, LOSS_TRACE_TAG, loss)
            self.acc_loss = 0


class SpeedHook(TraceHook):
    def __init__(self, iter_interval, batch_size, summary_writer=None):
        super(SpeedHook, self).__init__(summary_writer)
        self.iter_interval = iter_interval
        self.batch_size = batch_size
        self.t0 = time.time()
        self.num_examples = iter_interval * batch_size
        self.iter = 0

    def __call__(self, sess, epoch, model, loss):
        self.iter += 1
        if not self.iter == 0 and self.iter % self.iter_interval == 0:
            diff = time.time() - self.t0
            speed = "%.2f" % (self.num_examples / diff)
            print("Epoch " + str(epoch) +
                  "\tIter " + str(self.iter) +
                  "\tExamples/s " + str(speed))
            self.update_summary(sess, self.iter, SPEED_TRACE_TAG, float(speed))
            self.t0 = time.time()


class AccuracyHook(TraceHook):
    def __init__(self, batches, predict, target, at_every_epoch=1,
                 placeholders=None, summary_writer=None):
        super(AccuracyHook, self).__init__(summary_writer)
        self.batches = batches
        self.predict = predict
        self.target = target
        self.at_every_epoch = at_every_epoch
        self.placeholders = placeholders
        self.done_for_epoch = False
        self.iter = 0

    def __call__(self, sess, epoch, model, loss):
        self.iter += 1
        if epoch % self.at_every_epoch == 0:
            if not self.done_for_epoch:
                total = 0
                correct = 0

                for i, batch in enumerate(self.batches):
                    if self.placeholders is not None:
                        feed_dict = dict(zip(self.placeholders, batch))
                    else:
                        feed_dict = batch

                    predicted = sess.run(self.predict, feed_dict=feed_dict)
                    correct += sum(feed_dict[self.target] == predicted)
                    total += len(predicted)

                acc = float(correct) / total
                self.update_summary(sess, self.iter, ACCURACY_TRACE_TAG, acc)
                print("Epoch " + str(epoch) +
                      "\tAcc " + str(acc) +
                      "\tCorrect " + str(correct) + "\tTotal " + str(total))
                self.done_for_epoch = True
        else:
            self.done_for_epoch = False


class PRF1Hook(Hook):
    """
    Evaluate per-class and average precision, recall, F1
    """
    def __init__(self, batcher, placeholders, at_every_epoch):
        self.batcher = batcher
        self.placeholders = placeholders
        self.at_every_epoch = at_every_epoch

    def __call__(self, sess, epoch, iter, model, loss):
        if iter == 0 and epoch % self.at_every_epoch == 0:
            total = 0
            correct = 0
            truth_all = []
            pred_all = []
            for values in self.batcher:
                total += len(values[-1])
                feed_dict = {}
                for i in range(0, len(self.placeholders)):
                    feed_dict[self.placeholders[i]] = values[i]
                truth = np.argmax(values[-1], 1)
                predicted = sess.run(tf.arg_max(tf.nn.softmax(model), 1), feed_dict=feed_dict)
                correct += sum(truth == predicted)
                truth_all.extend(truth)
                pred_all.extend(predicted)
            print(classification_report(truth_all, pred_all, digits=4))  # target_names=["NEUTRAL", "AGAINST", "FAVOR"],


class SaveModelHook(Hook):
    def __init__(self, path, at_epoch, at_every_epoch=0):
        self.path = path + "/"
        self.at_epoch = at_epoch
        self.at_every_epoch = at_every_epoch

        # fixme: don't save optimizer parameters
        # self.saver = tf.train.Saver(tf.all_variables())
        self.saver = tf.train.Saver(tf.trainable_variables())

    def __call__(self, sess, epoch, iter, model, loss):
        if epoch == self.at_epoch:
            print("Saving model...")
            # todo
            pass
            #save_model(self.saver, sess, self.path, model, None)


class LoadModelHook(Hook):
    def __init__(self, path, at_epoch, at_every_epoch=0):
        self.path = path + "/"
        self.at_epoch = at_epoch
        self.at_every_epoch = at_every_epoch
        self.saver = tf.train.Saver(tf.all_variables())

    def __call__(self, sess, epoch, iter, model, loss):
        if epoch == self.at_epoch:
            print("Loading model...")
            # todo
            pass
            #model = load_model(sess, self.path + "latest/")