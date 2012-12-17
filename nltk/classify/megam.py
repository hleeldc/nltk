# Natural Language Toolkit: Interface to Megam Classifier
#
# Copyright (C) 2001-2012 NLTK Project
# Author: Edward Loper <edloper@gradient.cis.upenn.edu>
# URL: <http://www.nltk.org/>
# For license information, see LICENSE.TXT

"""
A set of functions used to interface with the external megam_ maxent
optimization package. Before megam can be used, you should tell NLTK where it
can find the megam binary, using the ``config_megam()`` function. Typical
usage:

    >>> from nltk.classify import megam
    >>> megam.config_megam() # pass path to megam if not found in PATH # doctest: +SKIP
    [Found megam: ...]

Use with MaxentClassifier. Example below, see MaxentClassifier documentation
for details.

    nltk.classify.MaxentClassifier.train(corpus, 'megam')

.. _megam: http://www.cs.utah.edu/~hal/megam/
"""
from __future__ import print_function, unicode_literals

import os
import os.path
import subprocess

from nltk import compat
from nltk.internals import find_binary
try:
    import numpy
except ImportError:
    numpy = None

######################################################################
#{ Configuration
######################################################################

_megam_bin = None
def config_megam(bin=None):
    """
    Configure NLTK's interface to the ``megam`` maxent optimization
    package.

    :param bin: The full path to the ``megam`` binary.  If not specified,
        then nltk will search the system for a ``megam`` binary; and if
        one is not found, it will raise a ``LookupError`` exception.
    :type bin: str
    """
    global _megam_bin
    _megam_bin = find_binary(
        'megam', bin,
        env_vars=['MEGAM',  'MEGAMHOME'],
        binary_names=['megam.opt', 'megam', 'megam_686', 'megam_i686.opt'],
        url='http://www.cs.utah.edu/~hal/megam/')

######################################################################
#{ Megam Interface Functions
######################################################################

def write_megam_file(train_toks, encoding, stream,
                     bernoulli=True, explicit=True, bin_stream=False):
    """
    Generate an input file for ``megam`` based on the given corpus of
    classified tokens.

    :type train_toks: list(tuple(dict, str))
    :param train_toks: Training data, represented as a list of
        pairs, the first member of which is a feature dictionary,
        and the second of which is a classification label.

    :type encoding: MaxentFeatureEncodingI
    :param encoding: A feature encoding, used to convert featuresets
        into feature vectors. May optionally implement a cost() method
        in order to assign different costs to different class predictions.

    :type stream: stream
    :param stream: The stream to which the megam input file should be
        written.

    :param bernoulli: If true, then use the 'bernoulli' format.  I.e.,
        all joint features have binary values, and are listed iff they
        are true.  Otherwise, list feature values explicitly.  If
        ``bernoulli=False``, then you must call ``megam`` with the
        ``-fvals`` option.

    :param explicit: If true, then use the 'explicit' format.  I.e.,
        list the features that would fire for any of the possible
        labels, for each token.  If ``explicit=True``, then you must
        call ``megam`` with the ``-explicit`` option.

    :type bin_stream: boolean
    :param bin_stream: Indicates whether the stream expects unicode
        string or bytes sequence.
    """
    # Look up the set of labels.
    labels = encoding.labels()
    labelnum = dict([(label, i) for (i, label) in enumerate(labels)])

    if bin_stream == True:
        class BytesWriter:
            def __init__(self, stream):
                self.stream = stream
            def write(self, s):
                self.stream.write(s.encode('utf-8'))
        stream = BytesWriter(stream)

    # Write the file, which contains one line per instance.
    for featureset, label in train_toks:
        # First, the instance number (or, in the weighted multiclass case, the cost of each label).
        if hasattr(encoding,'cost'):
            stream.write(':'.join(str(encoding.cost(featureset, label, l)) for l in labels))
        else:
            stream.write('%d' % labelnum[label])

        # For implicit file formats, just list the features that fire
        # for this instance's actual label.
        if not explicit:
            _write_megam_features(encoding.encode(featureset, label),
                                  stream, bernoulli)

        # For explicit formats, list the features that would fire for
        # any of the possible labels.
        else:
            for l in labels:
                stream.write(' #')
                _write_megam_features(encoding.encode(featureset, l),
                                      stream, bernoulli)

        # End of the instance.
        stream.write('\n')

def parse_megam_weights(s, features_count, explicit=True):
    """
    Given the stdout output generated by ``megam`` when training a
    model, return a ``numpy`` array containing the corresponding weight
    vector.  This function does not currently handle bias features.
    """
    if numpy is None:
        raise ValueError('This function requires that numpy be installed')
    assert explicit, 'non-explicit not supported yet'
    lines = s.decode('utf-8').strip().split('\n')
    weights = numpy.zeros(features_count, 'd')
    for line in lines:
        if line.strip():
            fid, weight = line.split()
            weights[int(fid)] = float(weight)
    return weights

def _write_megam_features(vector, stream, bernoulli):
    if not vector:
        raise ValueError('MEGAM classifier requires the use of an '
                         'always-on feature.')
    for (fid, fval) in vector:
        if bernoulli:
            if fval == 1:
                stream.write(' %s' % fid)
            elif fval != 0:
                raise ValueError('If bernoulli=True, then all'
                                 'features must be binary.')
        else:
            stream.write(' %s %s' % (fid, fval))

def call_megam(args):
    """
    Call the ``megam`` binary with the given arguments.
    """
    if isinstance(args, compat.string_types):
        raise TypeError('args should be a list of strings')
    if _megam_bin is None:
        config_megam()

    # Call megam via a subprocess
    cmd = [_megam_bin] + args
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    (stdout, stderr) = p.communicate()

    # Check the return code.
    if p.returncode != 0:
        print()
        print(stderr)
        raise OSError('megam command failed!')

    return stdout

