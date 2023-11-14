#ifndef QDT_GF2_H
#define QDT_GF2_H

#include <inttypes.h>

/* == configuration ==*/

#ifndef GF2_BITS
#define GF2_BITS 16
#endif // GF2_BITS

/* GF2_MSB(X) must zero all bits in X except most significant.
It must be defined externally if GF2_BITS > 64.
*/
#ifndef GF2_MSB
#define GF2_MSB(X) (gf2_msb)(X)
#endif // GF2_MSB

/* Memory back-end */
#ifndef GF2_MALLOC
#include <malloc.h>
#define GF2_MALLOC(S) ((malloc)(S))
#endif // GF2_MALLOC

#ifndef GF2_FREE
#include <malloc.h>
#define GF2_FREE(A) ((free)(A))
#endif // GF2_FREE

/* == definitions == */

#define _GLUE(A, B) A ## B
#define GLUE(A, B) _GLUE(A, B)
#define GLUE3(A, B, C) GLUE(GLUE(A, B), C)

#define GF2PRId GLUE(PRId, GF2_BITS)
#define GF2PRIu GLUE(PRIu, GF2_BITS)
#define GF2PRIx GLUE(PRIx, GF2_BITS)

#define GF2SCNd GLUE(SCNd, GF2_BITS)
#define GF2SCNu GLUE(SCNu, GF2_BITS)
#define GF2SCNx GLUE(SCNx, GF2_BITS)

/* gf2_t is an UNSIGNED element of GF[2^n], where n <= bit length of gf2_t */
typedef GLUE3(uint, GF2_BITS, _t) gf2_t;
/* gf2int_t is A SIGNED integer long enough to enumerate all elements of
 GF[2^n] with both signs */
typedef GLUE3(int, GF2_BITS, _t) gf2int_t;

static inline gf2_t gf2_msb(gf2_t x)
{
	x |= x >> 1;
	x |= x >> 2;
	x |= x >> 4;
#if GF2_BITS > 8
	x |= x >> 8;
#endif
#if GF2_BITS > 16
	x |= x >> 16;
#endif
#if GF2_BITS > 32
	x |= x >> 32;
#endif
	return x ^ (x >> 1);
}

typedef struct {
	gf2_t
		p,
		p_msb;
	gf2int_t mask;

	gf2_t *pow2;
	gf2int_t *log2;
} GF2;

typedef enum {
	GF2_OK = 0,
	/* zero or 1 generator */
	GF2_BAD_GENERATOR,
	/* log2(0) */
	GF2_LOG2_ZERO,
	/* log2(x) where x >= generator p, i.e. such x is impossible */
	GF2_P_LE_X,
	GF2_DIV_BY_ZERO,
	GF2_ERRORS
} GFResult;

static inline GFResult gf2_mul_slow(GF2 *gf, gf2_t *res, gf2_t a, gf2_t b)
{
	if (gf->p < 2) {
		return GF2_BAD_GENERATOR;
	}
	if (a == 0 || b == 0) {
		*res = 0;
		return GF2_OK;
	}

	/* multiply polynomials */
	gf2_t
		t = b,
		s = 0;

	while (t) {
		if (t & 1) {
			s ^= a;
		}
		a <<= 1;
		t >>= 1;
	}

	/* take product modulo generator p */
	gf2_t
		s_msb = GF2_MSB(s),
		p = gf->p,
		p_msb = gf->p_msb;

	gf2_t orig_p_msb = p_msb;

	while (p_msb < s_msb) {
		p_msb <<= 1;
		p <<= 1;
	}

	while (orig_p_msb <= p_msb) {
		if (p_msb & s) {
			s ^= p;
		}
		p_msb >>= 1;
		p >>= 1;
	}

	*res = s;
	return GF2_OK;
}

static inline GFResult gf2_init(GF2 *gf, gf2_t p)
{
	gf->p = p;
	if (p < 2) {
		gf->pow2 = NULL;
		gf->log2 = NULL;
		return GF2_BAD_GENERATOR;
	}

	gf2int_t
		size,
		x_mask;

	gf->p_msb = GF2_MSB(p);
	size = gf->p_msb;
	gf->mask = x_mask = size - 1;
	gf->pow2 = GF2_MALLOC(size * sizeof(*gf->pow2));
	gf->log2 = GF2_MALLOC(size * sizeof(*gf->log2));

	gf->pow2[0] = 1;
	gf->pow2[1] = 2;
	gf->log2[1] = 0;
	for (gf2int_t k = 1; k < x_mask; k++)
	{
		gf->log2[gf->pow2[k]] = k;
		gf2_mul_slow(gf, &gf->pow2[k + 1], gf->pow2[k], 2);
	}
	gf->pow2[x_mask] = 1;
	return GF2_OK;
}

static inline void gf2_deinit(GF2 *gf)
{
	if (gf->pow2 != NULL) {
		GF2_FREE(gf->pow2);
	}
	if (gf->log2 != NULL) {
		GF2_FREE(gf->log2);
	}
}

static inline void gf2_pow2(GF2 *gf, gf2_t *res, gf2int_t k)
{
	*res = gf->pow2[k & gf->mask];
}

static inline GFResult gf2_log2(GF2 *gf, gf2int_t *res, gf2_t x)
{
	if (x == 0) {
		return GF2_LOG2_ZERO;
	}
	if (gf->p <= x) {
		return GF2_P_LE_X;
	}
	*res = gf->log2[x];
	return GF2_OK;
}

static inline GFResult gf2_mul(GF2 *gf, gf2_t *res, gf2_t a, gf2_t b)
{
	if (a == 0 || b == 0) {
		*res = 0;
		return GF2_OK;
	}
	gf2int_t log2a, log2b;
	return (
		gf2_log2(gf, &log2a, a)
		|| gf2_log2(gf, &log2b, b)
		|| (gf2_pow2(gf, res, log2a + log2b), GF2_OK)
	);
}

static inline GFResult gf2_div(GF2 *gf, gf2_t *res, gf2_t a, gf2_t b)
{
	if (b == 0) {
		return GF2_DIV_BY_ZERO;
	}
	if (a == 0) {
		*res = 0;
		return GF2_OK;
	}
	gf2int_t log2a, log2b;
	return (
		gf2_log2(gf, &log2a, a)
		|| gf2_log2(gf, &log2b, b)
		|| (gf2_pow2(gf, res, log2a - log2b), GF2_OK)
	);
}

static inline GFResult gf2_pow(GF2 *gf, gf2_t *res, gf2_t a, gf2int_t k)
{
	if (k == 0) {
		*res = 1;
		return GF2_OK;
	}
	if (a == 0) {
		*res = 0;
		return GF2_OK;
	}
	gf2int_t log2a;
	return (
		gf2_log2(gf, &log2a, a)
		|| (gf2_pow2(gf, res, log2a * k), GF2_OK)
	);
}

#endif // QDT_GF2_H
