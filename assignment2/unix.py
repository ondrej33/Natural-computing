import os
import itertools
from statistics import mean
from auc import auc

TEST_PACKAGE = 'unm'  # 'cert' or 'unm'
TEST_NUMBER = '1'  # 1 or 2, 3
SLIDING_WINDOW = False
CHUNK_SIZE = 10
MAX_R = 5
K_FLAG = False
# -----------------------
assert MAX_R <= CHUNK_SIZE, "r !<= n"
# -----------------------
FP_ALPHABET = f'syscalls/snd-{TEST_PACKAGE}/snd-{TEST_PACKAGE}.alpha'
FP_RESULTS = f"results/unix_{CHUNK_SIZE}_{TEST_PACKAGE}{TEST_NUMBER}{'_sw' if SLIDING_WINDOW else ''}{'_k' if K_FLAG else ''}.txt"
FP_IMAGE = f"results/unix_{CHUNK_SIZE}_{TEST_PACKAGE}{TEST_NUMBER}{'_sw' if SLIDING_WINDOW else ''}{'_k' if K_FLAG else ''}.png"
FP_TRAIN = f"syscalls/snd-{TEST_PACKAGE}/snd-{TEST_PACKAGE}.train"
FP_MERGED_TEST = f"syscalls/snd-{TEST_PACKAGE}/snd-{TEST_PACKAGE}.{TEST_NUMBER}.test"
FP_MERGED_LABELS = f"syscalls/snd-{TEST_PACKAGE}/snd-{TEST_PACKAGE}.{TEST_NUMBER}.labels"
FP_TRAIN_CHUNKED = f"syscalls/snd-{TEST_PACKAGE}/snd-{TEST_PACKAGE}.chunked.train"
FP_TEST_CHUNKED = f"syscalls/snd-{TEST_PACKAGE}/snd-{TEST_PACKAGE}.chunked.test"


def split_file_to_chunks(f_path, labels_path=None, sliding_window=False):
    with open(f_path, "r") as f:
        f_content = f.read()
        f_lines = f_content.split("\n")[:-1]
    if labels_path:
        with open(labels_path, "r") as f:
            labels_content = f.read()
            labels_lines = labels_content.split("\n")[:-1]

    chunked_lines = []
    chunked_labels = []
    for j, l in enumerate(f_lines):
        chunks = []

        # skip small sequences
        if len(l) < CHUNK_SIZE:
            # print("skipping sequence < CHUNK_SIZE ...")
            continue

        # use sliding window or nonoverlap window for split sequence into chunks
        if sliding_window:
            for i in range(len(l) - CHUNK_SIZE + 1):
                chunks.append(l[i:i + CHUNK_SIZE])
        else:
            # non overlaping chunks where last part is omitted if it is not equal to chunk size (if sequence_len modulo CHUNK SIZE != 0)
            chunks = [l[i:i + CHUNK_SIZE] for i in range(0, len(l), CHUNK_SIZE) if len(l[i:i + CHUNK_SIZE]) == CHUNK_SIZE]
        chunked_lines.append(chunks)

        # if test set, append labels as well
        if labels_path:
            chunked_labels.append(len(chunks) * [labels_lines[j]])

    return chunked_lines, chunked_labels


if __name__ == "__main__":
    # split files into chunks
    train_chunked_lines, _ = split_file_to_chunks(FP_TRAIN, None, SLIDING_WINDOW)
    test_chunked_lines, test_chunked_labels = split_file_to_chunks(FP_MERGED_TEST, FP_MERGED_LABELS, SLIDING_WINDOW)
    test_chunk_sizes = [len(line) for line in test_chunked_lines]

    # save chunked files
    with open(FP_TRAIN_CHUNKED, "w") as f:
        f.write("\n".join(["\n".join(line) for line in train_chunked_lines]))
    with open(FP_TEST_CHUNKED, "w") as f:
        f.write("\n".join(["\n".join(line) for line in test_chunked_lines]))

    # ========= TRAIN + EVALUATE =========
    aucs = []
    for r_val in range(1, MAX_R+1):
        # generate scores
        bash_command = f"java -jar negsel2.jar -alphabet file://{FP_ALPHABET} {'-k' if K_FLAG else ''} -l -c -n {CHUNK_SIZE} -r {r_val} -self {FP_TRAIN_CHUNKED} < {FP_TEST_CHUNKED}"
        data = os.popen(bash_command).read()
        data_floats = [float(x) for x in data.split()]

        # flatten the list
        data_labels = [int(element) for sublist in test_chunked_labels for element in sublist]

        # merge by sequences by averaging
        reduced_list = list(map(lambda x: mean(data_floats[x[1]-x[0]:x[1]]), zip(test_chunk_sizes, itertools.accumulate(test_chunk_sizes))))
        reduced_labels = list(map(lambda x: int(x[0]),test_chunked_labels))
        # print("number of sequences in test size after merging:", len(reduced_list), "-", len(reduced_labels))
        # print(list(zip(reduced_list, reduced_labels)))
        # print(list(zip(data_floats, data_labels)))

        auc_value = auc(list(zip(reduced_list, reduced_labels)), r_val, FP_IMAGE, MAX_R)
        # auc_value = auc(list(zip(data_floats, data_labels)), r_val, FP_IMAGE, MAX_R)
        aucs.append(str(auc_value))
        print(f"{r_val}:  {auc_value}")

    with open(FP_RESULTS, "w") as f:
        f.write("\n".join(aucs))