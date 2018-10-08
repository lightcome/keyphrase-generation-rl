import torch
from sequence_generator import SequenceGenerator
import logging
import config
from pykp.io import KeyphraseDataset
from torch.utils.data import DataLoader
import time
from utils.time_log import time_since
from evaluate import evaluate_beam_search, prediction_by_sampling
import pykp.io
import sys
import argparse
from utils.data_loader import load_data_and_vocab
from pykp.model import Seq2SeqModel
import os

def init_pretrained_model(opt):
    model = Seq2SeqModel(opt)
    model.load_state_dict(torch.load(opt.model))
    model.to(opt.device)
    model.eval()
    return model

def main(opt):
    try:
        start_time = time.time()
        load_data_time = time_since(start_time)
        test_data_loader, word2idx, idx2word, vocab = load_data_and_vocab(opt, load_train=False)
        model = init_pretrained_model(opt)
        logging.info('Time for loading the data and model: %.1f' % load_data_time)

        if opt.delimiter_type == 0:
            delimiter_word = pykp.io.SEP_WORD
        else:
            delimiter_word = pykp.io.EOS_WORD

        start_time = time.time()
        generator = SequenceGenerator(model,
                                      bos_idx=opt.word2idx[pykp.io.BOS_WORD],
                                      eos_idx=opt.word2idx[pykp.io.EOS_WORD],
                                      pad_idx=opt.word2idx[pykp.io.PAD_WORD],
                                      beam_size=opt.beam_size,
                                      max_sequence_length=opt.max_length,
                                      copy_attn=opt.copy_attention,
                                      coverage_attn=opt.coverage_attn,
                                      review_attn=opt.review_attn,
                                      include_attn_dist=opt.include_attn_dist,
                                      length_penalty_factor=opt.length_penalty_factor,
                                      coverage_penalty_factor=opt.coverage_penalty_factor,
                                      length_penalty=opt.length_penalty,
                                      coverage_penalty=opt.coverage_penalty,
                                      cuda=opt.gpuid > -1,
                                      n_best=opt.n_best
                                      )
        if opt.one2many and opt.one2many_mode > 1:
            prediction_by_sampling(generator, test_data_loader, opt, delimiter_word)
        else:
            evaluate_beam_search(generator, test_data_loader, opt, delimiter_word)
        total_testing_time = time_since(start_time)
        logging.info('Time for a complete testing: %.1f' % total_testing_time)
        print('Time for a complete testing: %.1f' % total_testing_time)
        sys.stdout.flush()

    except Exception as e:
        logging.exception("message")
    return

    pass

if __name__=='__main__':
    # load settings for training
    parser = argparse.ArgumentParser(
        description='predict.py',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    config.model_opts(parser)
    config.predict_opts(parser)
    config.vocab_opts(parser)
    opt = parser.parse_args()

    if opt.seed > 0:
        torch.manual_seed(opt.seed)

    if torch.cuda.is_available():
        if not opt.gpuid:
            opt.gpuid = 0
        opt.device = torch.device("cuda:%d" % opt.gpuid)
    else:
        opt.device = torch.device("cpu")
        opt.gpuid = -1
        print("CUDA is not available, fall back to CPU.")

    opt.exp = 'predict.' + opt.exp
    if hasattr(opt, 'copy_attention') and opt.copy_attention:
        opt.exp += '.copy'

    if hasattr(opt, 'coverage_attn') and opt.coverage_attn:
        opt.exp += '.coverage'

    if hasattr(opt, 'bidirectional'):
        if opt.bidirectional:
            opt.exp += '.bi-directional'
    else:
        opt.exp += '.uni-directional'

    if opt.n_best < 0:
        opt.n_best = opt.beam_size

    # fill time into the name
    if opt.exp_path.find('%s') > 0:
        opt.exp_path = opt.exp_path % (opt.exp, opt.timemark)
        opt.pred_path = opt.pred_path % (opt.exp, opt.timemark)

    if not os.path.exists(opt.exp_path):
        os.makedirs(opt.exp_path)
    if not os.path.exists(opt.pred_path):
        os.makedirs(opt.pred_path)

    logging = config.init_logging(log_file=opt.exp_path + '/output.log', stdout=True)
    logging.info('Parameters:')
    [logging.info('%s    :    %s' % (k, str(v))) for k, v in opt.__dict__.items()]

    main(opt)
