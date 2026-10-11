"""Pure-Python LZO1X decompressor."""

def decompress(src, out_len=0):
    out = bytearray()
    ip = 0
    n = len(src)

    def copy_match(dist, length):
        start = len(out) - dist
        if dist >= length:
            out.extend(out[start:start + length])
        else:
            pat = bytes(out[start:])
            reps = length // dist + 1
            out.extend((pat * reps)[:length])

    t = src[ip]
    state = 'loop'
    if t > 17:
        ip += 1
        t -= 17
        if t < 4:
            state = 'match_next'
        else:
            out.extend(src[ip:ip + t]); ip += t
            state = 'first_literal'
    while True:
        if state == 'loop':
            t = src[ip]; ip += 1
            if t >= 16:
                state = 'match'; continue
            if t == 0:
                while src[ip] == 0:
                    t += 255; ip += 1
                t += 15 + src[ip]; ip += 1
            t += 3
            out.extend(src[ip:ip + t]); ip += t
            state = 'first_literal'
        if state == 'first_literal':
            t = src[ip]; ip += 1
            if t >= 16:
                state = 'match'
            else:
                dist = 1 + 0x0800 + (t >> 2) + (src[ip] << 2); ip += 1
                copy_match(dist, 3)
                state = 'match_done'
        if state == 'match':
            if t >= 64:
                dist = 1 + ((t >> 2) & 7) + (src[ip] << 3); ip += 1
                copy_match(dist, (t >> 5) + 1)
            elif t >= 32:
                t &= 31
                if t == 0:
                    while src[ip] == 0:
                        t += 255; ip += 1
                    t += 31 + src[ip]; ip += 1
                dist = 1 + (src[ip] >> 2) + (src[ip + 1] << 6); ip += 2
                copy_match(dist, t + 2)
            elif t >= 16:
                dist = (t & 8) << 11
                t &= 7
                if t == 0:
                    while src[ip] == 0:
                        t += 255; ip += 1
                    t += 7 + src[ip]; ip += 1
                dist += (src[ip] >> 2) + (src[ip + 1] << 6); ip += 2
                if dist == 0:
                    break
                dist += 0x4000
                copy_match(dist, t + 2)
            else:
                dist = 1 + (t >> 2) + (src[ip] << 2); ip += 1
                copy_match(dist, 2)
            state = 'match_done'
        if state == 'match_done':
            t = src[ip - 2] & 3
            if t == 0:
                state = 'loop'; continue
            state = 'match_next'
        if state == 'match_next':
            out.extend(src[ip:ip + t]); ip += t
            t = src[ip]; ip += 1
            state = 'match'
    return bytes(out)


def read_chunk(data, pos):
    """Decompress a UE3 compressed chunk (tag, blocksize, sizes, block table, blocks) at pos."""
    import struct
    tag, bs, csize, usize = struct.unpack_from('<IIII', data, pos)
    assert tag == 0x9E2A83C1, hex(tag)
    nb = (usize + bs - 1) // bs
    tbl = [struct.unpack_from('<II', data, pos + 16 + 8 * i) for i in range(nb)]
    p = pos + 16 + 8 * nb
    out = []
    for c, u in tbl:
        b = decompress(data[p:p + c], u)
        assert len(b) == u, (len(b), u)
        out.append(b); p += c
    return b''.join(out), p
