import os
import csv
import copy
import math
import collections


def rescale_samscore(u, nu, max_score, min_score):
    if min_score < 0:
        scaling_factor = 100.0 / max_score - min_score
    else:
        scaling_factor = 100.0 / max_score

    for read_index in u:
        if min_score < 0:
            u[read_index][1][0] = u[read_index][1][0] - min_score

        u[read_index][1][0] = math.exp(u[read_index][1][0] * scaling_factor)
        u[read_index][3] = u[read_index][1][0]

    for read_index in nu:
        nu[read_index][3] = 0.0

        for i in range(0, len(nu[read_index][1])):
            if min_score < 0:
                nu[read_index][1][i] = nu[read_index][1][i] - min_score

            nu[read_index][1][i] = math.exp(nu[read_index][1][i] * scaling_factor)

            if nu[read_index][1][i] > nu[read_index][3]:
                nu[read_index][3] = nu[read_index][1][i]

    return u, nu


def find_sam_align_score(fields):
    """
    Find the Bowtie2 alignment score for the given split line (``fields``).

    Searches the SAM fields for the ``AS:i`` substring and extracts the Bowtie2-specific alignment score. This will not
    work for other aligners.

    :param fields: a line that has been split on "\t"
    :type fields: list

    :return: the alignment score
    :rtype: float

    """
    read_length = float(len(fields[9]))

    for field in fields:
        if field.startswith("AS:i:"):
            a_score = int(field[5:])
            return a_score + read_length

    raise ValueError("Could not find alignment score")


def build_matrix(vta_path, p_score_cutoff=0.01):
    u = dict()
    nu = dict()

    h_read_id = {}
    h_ref_id = {}

    refs = []
    reads = []

    ref_count = 0
    read_count = 0

    max_score = 0
    min_score = 0

    with open(vta_path, "r") as handle:
        for line in handle:
            read_id, ref_id, pos, length, p_score = line.rstrip().split(",")

            p_score = float(p_score)

            if p_score < p_score_cutoff:
                continue

            min_score = min(min_score, p_score)
            max_score = max(max_score, p_score)

            ref_index = h_ref_id.get(ref_id, -1)

            if ref_index == -1:
                ref_index = ref_count
                h_ref_id[ref_id] = ref_index
                refs.append(ref_id)
                ref_count += 1

            read_index = h_read_id.get(read_id, -1)

            if read_index == -1:
                # hold on this new read. first, wrap previous read profile and see if any previous read has a same
                # profile with that!
                read_index = read_count
                h_read_id[read_id] = read_index
                reads.append(read_id)
                read_count += 1
                u[read_index] = [[ref_index], [p_score], [float(p_score)], p_score]
            else:
                if read_index in u:
                    if ref_index in u[read_index][0]:
                        continue
                    nu[read_index] = u[read_index]
                    del u[read_index]

                if ref_index in nu[read_index][0]:
                    continue

                nu[read_index][0].append(ref_index)
                nu[read_index][1].append(p_score)

                if p_score > nu[read_index][3]:
                    nu[read_index][3] = p_score

    u, nu = rescale_samscore(u, nu, max_score, min_score)

    for read_index in u:
        # keep ref_index and score only
        u[read_index] = [u[read_index][0][0], u[read_index][1][0]]

    for read_index in nu:
        p_score_sum = sum(nu[read_index][1])
        # Normalize p_score.
        nu[read_index][2] = [k / p_score_sum for k in nu[read_index][1]]

    return u, nu, refs, reads


def em(u, nu, genomes, max_iter, epsilon, pi_prior, theta_prior):
    genome_count = len(genomes)

    pi = [1. / genome_count] * genome_count
    init_pi = copy.copy(pi)
    theta = copy.copy(pi)

    pi_sum_0 = [0] * genome_count

    u_weights = [u[i][1] for i in u]

    max_u_weights = 0
    u_total = 0

    if u_weights:
        max_u_weights = max(u_weights)
        u_total = sum(u_weights)

    for i in u:
        pi_sum_0[u[i][0]] += u[i][1]

    nu_weights = [nu[i][3] for i in nu]

    max_nu_weights = 0
    nu_total = 0

    if nu_weights:
        max_nu_weights = max(nu_weights)
        nu_total = sum(nu_weights)

    prior_weight = max(max_u_weights, max_nu_weights)
    nu_length = len(nu)

    if nu_length == 0:
        nu_length = 1

    # EM iterations
    for i in range(max_iter):
        pi_old = pi
        theta_sum = [0 for k in genomes]

        # E Step
        for j in nu:
            z = nu[j]

            # A set of any genome mapping with j
            ind = z[0]

            # Get relevant pis for the read
            pi_tmp = [pi[k] for k in ind]

            # Get relevant thetas for the read.
            theta_tmp = [theta[k] for k in ind]

            # Calculate non-normalized xs
            x_tmp = [1. * pi_tmp[k] * theta_tmp[k] * z[1][k] for k in range(len(ind))]

            x_sum = sum(x_tmp)

            # Avoid dividing by 0 at all times.
            if x_sum == 0:
                x_norm = [0.0 for k in x_tmp]
            else:
                # Normalize new xs.
                x_norm = [1. * k / x_sum for k in x_tmp]

            # Update x in nu.
            nu[j][2] = x_norm

            for k in range(len(ind)):
                # Keep weighted running tally for theta
                theta_sum[ind[k]] += x_norm[k] * nu[j][3]

        # M step
        pi_sum = [theta_sum[k] + pi_sum_0[k] for k in range(len(theta_sum))]
        pip = pi_prior * prior_weight

        # Update pi.
        pi = [(1. * k + pip) / (u_total + nu_total + pip * len(pi_sum)) for k in pi_sum]

        if i == 0:
            init_pi = pi

        theta_p = theta_prior * prior_weight

        nu_total_div = nu_total

        if nu_total_div == 0:
            nu_total_div = 1

        theta = [(1. * k + theta_p) / (nu_total_div + theta_p * len(theta_sum)) for k in theta_sum]

        cutoff = 0.0

        for k in range(len(pi)):
            cutoff += abs(pi_old[k] - pi[k])

        if cutoff <= epsilon or nu_length == 1:
            break

    return init_pi, pi, theta, nu


def find_updated_score(nu, read_index, ref_index):
    try:
        index = nu[read_index][0].index(ref_index)
    except ValueError:
        return 0.0, 0.0

    p_score_sum = sum(nu[read_index][1]) / 100

    updated_pscore = nu[read_index][2][index]

    return updated_pscore, p_score_sum


def compute_best_hit(u, nu, refs, reads):
    ref_count = len(refs)

    best_hit_reads = [0.0] * ref_count
    level_1_reads = [0.0] * ref_count
    level_2_reads = [0.0] * ref_count

    for i in u:
        best_hit_reads[u[i][0]] += 1
        level_1_reads[u[i][0]] += 1

    for j in nu:
        z = nu[j]
        ind = z[0]
        x_norm = z[2]
        best_ref = max(x_norm)
        num_best_ref = 0

        for i in range(len(x_norm)):
            if x_norm[i] == best_ref:
                num_best_ref += 1

        num_best_ref = num_best_ref or 1

        for i in range(len(x_norm)):
            if x_norm[i] == best_ref:
                best_hit_reads[ind[i]] += 1.0 / num_best_ref

                if x_norm[i] >= 0.5:
                    level_1_reads[ind[i]] += 1
                elif x_norm[i] >= 0.01:
                    level_2_reads[ind[i]] += 1

    ref_count = len(refs)
    read_count = len(reads)

    best_hit = [best_hit_reads[k] / read_count for k in range(ref_count)]
    level_1 = [level_1_reads[k] / read_count for k in range(ref_count)]
    level_2 = [level_2_reads[k] / read_count for k in range(ref_count)]

    return best_hit_reads, best_hit, level_1, level_2


def reassign(sam_path, p_score_cutoff=0.01, epsilon=1e-7, pi_prior=0, theta_prior=0, max_iter=30, report_path=None,
             realigned_path=None):

    u, nu, refs, reads = build_matrix(sam_path, p_score_cutoff)

    ref_count = len(refs)
    read_count = len(reads)

    best_hit_initial_reads, best_hit_initial, level_1_initial, level_2_initial = compute_best_hit(u, nu, refs, reads)

    init_pi, pi, _, nu = em(u, nu, refs, max_iter, epsilon, pi_prior, theta_prior)

    best_hit_final_reads, best_hit_final, level_1_final, level_2_final = compute_best_hit(u, nu, refs, reads)

    tmp = zip(
        pi,
        refs,
        init_pi,
        best_hit_initial,
        best_hit_initial_reads,
        best_hit_final,
        best_hit_final_reads,
        level_1_initial,
        level_2_initial,
        level_1_final,
        level_2_final
    )

    tmp = sorted(tmp, reverse=True)

    x1, x2, x3, x4, x5, x6, x7, x8, x9, x10, x11 = zip(*tmp)

    no_cutoff = False

    for i in range(len(x10)):
        if not no_cutoff and x1[i] < 0.01 and x10[i] <= 0 and x11[i] <= 0:
            break

        if i == (len(x10) - 1):
            i += 1

    # Changing the column order here
    tmp = zip(
        x2[:i],
        x1[:i],
        x6[:i],
        x7[:i],
        x10[:i],
        x11[:i],
        x3[:i],
        x4[:i],
        x5[:i],
        x8[:i],
        x9[:i]
    )

    if report_path:
        with open(report_path, "w") as handle:
            csv_writer = csv.writer(handle, delimiter='\t')

            header = [
                "Genome",
                "Final Guess",
                "Final Best Hit",
                "Final Best Hit Read Numbers",
                "Final High Confidence Hits",
                "Final Low Confidence Hits",
                "Initial Guess",
                "Initial Best Hit",
                "Initial Best Hit Read Numbers",
                "Initial High Confidence Hits",
                "Initial Low Confidence Hits"
            ]

            header1 = ["Total Number of Aligned Reads:", read_count, "Total Number of Mapped Genomes:", ref_count]

            csv_writer.writerow(header1)
            csv_writer.writerow(header)
            csv_writer.writerows(tmp)

    if realigned_path:
        rewrite_align(u, nu, sam_path, p_score_cutoff, realigned_path)

    return report_path, x2, x3, x4, x5, x1, x6, x7, x8, x9, x10, x11, realigned_path


def rewrite_align(u, nu, sam_path, p_score_cutoff, path):
    with open(sam_path, "r") as old_handle:
        with open(path, "w") as new_handle:
            h_read_id = {}
            h_ref_id = {}

            refs = []
            reads = []

            ref_count = 0
            read_count = 0

            for line in old_handle:
                if line[0] in ["@", "#"]:
                    new_handle.write(line)
                    continue

                fields = line.split("\t")

                read_id = fields[0]
                ref_id = fields[2]

                # Bitwise FLAG - 0x4 : segment unmapped
                if int(fields[1]) & 0x4 == 4:
                    continue

                if ref_id == "*":
                    continue

                p_score = find_sam_align_score(fields)

                # Skip if the p_score does not meet the minimum cutoff.
                if p_score < p_score_cutoff:
                    continue

                ref_index = h_ref_id.get(ref_id, -1)

                if ref_index == -1:
                    ref_index = ref_count
                    h_ref_id[ref_id] = ref_index
                    refs.append(ref_id)
                    ref_count += 1

                read_index = h_read_id.get(read_id, -1)

                if read_index == -1:
                    # hold on this new read
                    # first, wrap previous read profile and see if any previous read has a same profile with that!
                    read_index = read_count
                    h_read_id[read_id] = read_index
                    reads.append(read_id)
                    read_count += 1

                    if read_index in u:
                        new_handle.write(line)
                        continue

                if read_index in nu:
                    updated_score, p_score_sum = find_updated_score(nu, read_index, ref_index)

                    if updated_score < p_score_cutoff:
                        continue

                    if updated_score >= 1.0:
                        updated_score = 0.999999

                    mapq2 = math.log10(1 - updated_score)

                    fields[4] = str(int(round(-10.0 * mapq2)))

                    new_handle.write("\t".join(fields))

    return path


def subtract(analysis_path, host_scores):
    subtracted_count = 0

    vta_path = os.path.join(analysis_path, "to_isolates.vta")

    isolates_high_scores = collections.defaultdict(int)

    with open(vta_path, "r") as handle:
        for line in handle:
            read_id = line[0]
            isolates_high_scores[read_id] = max(isolates_high_scores[read_id], int(line[4]))

    out_path = os.path.join(analysis_path, "subtracted.vta")

    with open(out_path, "w") as handle:
        for line in handle:
            line = line.decode()
            read_id = line[0]
            if host_scores.get(read_id, 0) >= isolates_high_scores[read_id]:
                subtracted_count += 1
                handle.write(line)

    os.remove(vta_path)

    return subtracted_count


def coverage(sam, ref_lengths):
    align = dict()

    for read_id, ref_id, pos, length, p_score, a_score in sam.entries():
        if ref_id not in ref_lengths:
            continue

        if ref_id not in align:
            align[ref_id] = [0] * ref_lengths[ref_id]

        for i in range(pos, pos + length):
            try:
                align[ref_id][i] += 1
            except IndexError:
                pass

    depth = dict()

    for ref_id, ref in align.items():
        length = len(ref)

        depth[ref_id] = {
            "coverage": 1 - ref.count(0) / length,
            "depth": sum(ref) / length,
            "align": ref
        }

    return depth
