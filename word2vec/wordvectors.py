from __future__ import division, print_function, unicode_literals

import numpy as np

try:
    from sklearn.externals import joblib
except:
    joblib = None

from word2vec.utils import unitvec


class WordVectors(object):

    def __init__(self, vocab, vectors, clusters=None):
        """
        Initialize a WordVectors class based on vocabulary and vectors

        This initializer precomputes the vectors of the vectors

        Parameters
        ----------
        vocab : np.array
            1d array with the vocabulary
        vectors : np.array
            2d array with the vectors calculated by word2vec
        clusters : word2vec.WordClusters (optional)
            1d array with the clusters calculated by word2vec
        """
        self.vocab = vocab
        self.vectors = vectors
        self.clusters = clusters

        self.vocab_hash = {}
        for i, word in enumerate(vocab):
            self.vocab_hash[word] = i

    def ix(self, word):
        """
        Returns the index on self.vocab and `self.vectors` for `word`
        """
        return self.vocab_hash[word]

    def word(self, ix):
        """Returns the word that corresponds to the index.

        Parameters
        -------
        ix : int
            The index of the word

        Returns
        -------
        str
            The word that corresponds to the index
        """
        return self.vocab[ix]

    def __getitem__(self, word):
        return self.get_vector(word)

    def __contains__(self, word):
        return word in self.vocab_hash

    def get_vector(self, word):
        """
        Returns the (vectors) vector for `word` in the vocabulary
        """
        idx = self.ix(word)
        return self.vectors[idx]

    def get_word(self, vector):
        """Returns the word according to the vector

        Parameters
        -------
        vector : numpy.core.multiarray.array
            The representing vector of the word

        Returns
        -------
        str or None
            The word according to the specified vector if found, else None
        """
        word_index = np.where(np.all(self.vectors == vector, axis=1))[0]
        return self.word(word_index[0]) if word_index.size else None

    def cosine(self, word, n=10):
        """
        Cosine similarity.

        metric = dot(vectors_of_vectors, vectors_of_target_vector)
        Uses a precomputed vectors of the vectors

        Parameters
        ----------
        word : string
        n : int, optional (default 10)
            number of neighbors to return

        Returns
        -------
        2 numpy.array:
            1. position in self.vocab
            2. cosine similarity
        """
        metrics = np.dot(self.vectors, self[word].T)
        best = np.argsort(metrics)[::-1][1:n+1]
        best_metrics = metrics[best]
        return best, best_metrics

    def get_sum_vector(self, vectors):
        combined = None
        for vector in vectors:
            if combined is None:
                combined = vector
            else:
                combined = np.add(combined, vector)
        if combined is not None:
            combined = combined / np.linalg.norm(combined)
        return combined

    def safe_get_vector(self, word):
        try:
            return self[word].T
        except:
            return None

    def get_sum_word_vector(self, words):
        vectors = filter(lambda x: x is not None,
                         [self.safe_get_vector(word) for word in words])
        return self.get_sum_vector(vectors)

    def exclude_words_from_result_vector(self, best, words):
        exclude_idx = [np.where(best == self.ix(word)) for word in words if
                       self.ix(word) in best]
        best = np.delete(best, exclude_idx)
        return best

    def cosine_multi(self, words, n=10):
        combined = self.get_sum_word_vector(words) if len(words) > 1 else self[words[0]].T
        metrics = np.dot(self.vectors, combined)
        best = np.argsort(metrics)[::-1][1:n+len(words)]
        if len(words) > 1:
            best = self.exclude_words_from_result_vector(best, words)
        best_metrics = metrics[best]
        return best, best_metrics

    def cosine_raw(self, words, n=10):
        combined = self.get_sum_word_vector(words) if len(words) > 1 \
            else self.safe_get_vector(words[0])
        if combined is not None:
            metrics = np.dot(self.vectors, combined)
            return metrics
        return None

    def analogy(self, pos, neg, n=10):
        """
        Analogy similarity.

        Parameters
        ----------
        pos : list
        neg : list

        Returns
        -------
        2 numpy.array:
            1. position in self.vocab
            2. cosine similarity

        Example
        -------
            `king - man + woman = queen` will be:
            `pos=['king', 'woman'], neg=['man']`
        """
        exclude = pos + neg
        pos = [(word, 1.0) for word in pos]
        neg = [(word, -1.0) for word in neg]

        mean = []
        for word, direction in pos + neg:
            mean.append(direction * self[word])
        mean = np.array(mean).mean(axis=0)

        metrics = np.dot(self.vectors, mean)
        best = metrics.argsort()[::-1][:n + len(exclude)]

        exclude_idx = [np.where(best == self.ix(word)) for word in exclude if
                       self.ix(word) in best]
        new_best = np.delete(best, exclude_idx)
        best_metrics = metrics[new_best]
        return new_best[:n], best_metrics[:n]

    def generate_response(self, indexes, metrics, clusters=True):
        '''
        Generates a pure python (no numpy) response based on numpy arrays
        returned by `self.cosine` and `self.analogy`
        '''
        if self.clusters and clusters:
            return np.rec.fromarrays((indexes, self.vocab[indexes], metrics,
                                      self.clusters.clusters[indexes]),
                                     names=('index', 'word', 'metric', 'cluster'))
        else:
            return np.rec.fromarrays((indexes, self.vocab[indexes], metrics),
                                     names=('index', 'word', 'metric'))

    def to_mmap(self, fname):
        if not joblib:
            raise Exception("sklearn is needed to save as mmap")

        joblib.dump(self, fname)

    @classmethod
    def from_binary(cls, fname, vocabUnicodeSize=78, desired_vocab=None, encoding="utf-8"):
        """
        Create a WordVectors class based on a word2vec binary file

        Parameters
        ----------
        fname : path to file
        vocabUnicodeSize: the maximum string length (78, by default)
        desired_vocab: if set, this will ignore any word and vector that
                       doesn't fall inside desired_vocab.

        Returns
        -------
        WordVectors instance
        """
        with open(fname, 'rb') as fin:
            header = fin.readline()
            vocab_size, vector_size = list(map(int, header.split()))

            vocab = np.empty(vocab_size, dtype='<U%s' % vocabUnicodeSize)
            vectors = np.empty((vocab_size, vector_size), dtype=np.float)
            binary_len = np.dtype(np.float32).itemsize * vector_size
            for i in range(vocab_size):
                # read word
                word = b''
                while True:
                    ch = fin.read(1)
                    if ch == b' ':
                        break
                    word += ch
                include = desired_vocab is None or word in desired_vocab
                if include:
                    vocab[i] = word.decode(encoding)

                # read vector
                vector = np.fromstring(fin.read(binary_len), dtype=np.float32)
                if include:
                    vectors[i] = unitvec(vector)
                fin.read(1)  # newline

            if desired_vocab is not None:
                vectors = vectors[vocab != '', :]
                vocab = vocab[vocab != '']
        return cls(vocab=vocab, vectors=vectors)

    @classmethod
    def from_text(cls, fname, vocabUnicodeSize=78, desired_vocab=None, encoding="utf-8"):
        """
        Create a WordVectors class based on a word2vec text file

        Parameters
        ----------
        fname : path to file
        vocabUnicodeSize: the maximum string length (78, by default)
        desired_vocab: if set, this will ignore any word and vector that
                       doesn't fall inside desired_vocab.

        Returns
        -------
        WordVectors instance
        """
        with open(fname, 'rb') as fin:
            header = fin.readline()
            vocab_size, vector_size = list(map(int, header.split()))

            vocab = np.empty(vocab_size, dtype='<U%s' % vocabUnicodeSize)
            vectors = np.empty((vocab_size, vector_size), dtype=np.float)
            for i, line in enumerate(fin):
                line = line.decode(encoding).strip()
                parts = line.split(' ')
                word = parts[0]
                include = desired_vocab is None or word in desired_vocab
                if include:
                    vector = np.array(parts[1:], dtype=np.float)
                    vocab[i] = word
                    vectors[i] = unitvec(vector)

            if desired_vocab is not None:
                vectors = vectors[vocab != '', :]
                vocab = vocab[vocab != '']
        return cls(vocab=vocab, vectors=vectors)

    @classmethod
    def from_mmap(cls, fname):
        """
        Create a WordVectors class from a memory map

        Parameters
        ----------
        fname : path to file

        Returns
        -------
        WordVectors instance
        """
        memmaped = joblib.load(fname, mmap_mode='r+')
        return cls(vocab=memmaped.vocab, vectors=memmaped.vectors)
