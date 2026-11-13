// SPDX-FileCopyrightText: 2026 Wells Riley
// SPDX-License-Identifier: GPL-3.0-or-later

// ####################################
// audio_gate_plugin.c
//
// ALSA plugin "audiogate", for audio_gate.py. It passes sound through to its
// slave untouched, and whenever a player writes something other than
// silence, it sends one byte to /run/audio-gate.sock. audio_gate.py then
// connects the speaker's audio pin, before the sound reaches it: players
// write ahead of the hardware, the emulators by about 0.19 s.
//
// Built on the Pi by setup.sh, and used from /etc/asound.conf:
//   cc -O2 -fPIC -shared -o libasound_module_pcm_audiogate.so audio_gate_plugin.c -lasound
//
// October 26, 2026 - https://wells.ee/projects/macintosh-mini/
// ####################################

#include <alsa/asoundlib.h>
#include <alsa/pcm_external.h>
#include <errno.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

typedef struct {
	snd_pcm_extplug_t ext;
	int fd;                  // datagram socket, or -1
	struct sockaddr_un addr;
	long threshold;          // samples within this of zero are silence
} gate_t;

// True if any sample is past the threshold. Formats are fixed to S16 below,
// so the plug in front of this converts whatever a player writes.
static int loud(const snd_pcm_channel_area_t *areas, snd_pcm_uframes_t offset,
		snd_pcm_uframes_t size, unsigned int channels, long threshold)
{
	for (unsigned int c = 0; c < channels; c++) {
		const snd_pcm_channel_area_t *a = &areas[c];
		const char *p = (const char *)a->addr + (a->first + a->step * offset) / 8;
		unsigned int step = a->step / 8;
		for (snd_pcm_uframes_t i = 0; i < size; i++, p += step) {
			int16_t v = *(const int16_t *)p;
			if (v > threshold || v < -threshold)
				return 1;
		}
	}
	return 0;
}

// Never blocks and never raises SIGPIPE: with no gate listening, or its queue
// full, the byte is dropped and the sound plays as it would without this.
static void notify(gate_t *g)
{
	if (g->fd >= 0)
		sendto(g->fd, "!", 1, MSG_DONTWAIT | MSG_NOSIGNAL,
		       (const struct sockaddr *)&g->addr, sizeof(g->addr));
}

static snd_pcm_sframes_t gate_transfer(snd_pcm_extplug_t *ext,
		const snd_pcm_channel_area_t *dst_areas, snd_pcm_uframes_t dst_offset,
		const snd_pcm_channel_area_t *src_areas, snd_pcm_uframes_t src_offset,
		snd_pcm_uframes_t size)
{
	gate_t *g = ext->private_data;

	snd_pcm_areas_copy(dst_areas, dst_offset, src_areas, src_offset,
			   ext->channels, size, SND_PCM_FORMAT_S16);
	if (loud(src_areas, src_offset, size, ext->channels, g->threshold))
		notify(g);
	return size;
}

static int gate_close(snd_pcm_extplug_t *ext)
{
	gate_t *g = ext->private_data;

	if (g->fd >= 0)
		close(g->fd);
	free(g);
	return 0;
}

static const snd_pcm_extplug_callback_t gate_callback = {
	.transfer = gate_transfer,
	.close = gate_close,
};

SND_PCM_PLUGIN_DEFINE_FUNC(audiogate)
{
	snd_config_iterator_t i, next;
	snd_config_t *slave = NULL;
	const char *path = "/run/audio-gate.sock";
	long threshold = 32;   // about -60 dBFS; emulators write exact zeros when quiet
	gate_t *g;
	int err;

	snd_config_for_each(i, next, conf) {
		snd_config_t *n = snd_config_iterator_entry(i);
		const char *id;

		if (snd_config_get_id(n, &id) < 0)
			continue;
		if (!strcmp(id, "comment") || !strcmp(id, "type") || !strcmp(id, "hint"))
			continue;
		if (!strcmp(id, "slave")) {
			slave = n;
			continue;
		}
		if (!strcmp(id, "socket")) {
			if (snd_config_get_string(n, &path) < 0) {
				SNDERR("audiogate: socket must be a string");
				return -EINVAL;
			}
			continue;
		}
		if (!strcmp(id, "threshold")) {
			if (snd_config_get_integer(n, &threshold) < 0) {
				SNDERR("audiogate: threshold must be an integer");
				return -EINVAL;
			}
			continue;
		}
		SNDERR("audiogate: unknown field %s", id);
		return -EINVAL;
	}
	if (!slave) {
		SNDERR("audiogate: no slave");
		return -EINVAL;
	}
	if (strlen(path) >= sizeof(g->addr.sun_path)) {
		SNDERR("audiogate: socket path too long");
		return -EINVAL;
	}

	g = calloc(1, sizeof(*g));
	if (!g)
		return -ENOMEM;
	g->threshold = threshold;
	g->addr.sun_family = AF_UNIX;
	strcpy(g->addr.sun_path, path);
	g->fd = socket(AF_UNIX, SOCK_DGRAM | SOCK_CLOEXEC | SOCK_NONBLOCK, 0);

	g->ext.version = SND_PCM_EXTPLUG_VERSION;
	g->ext.name = "audiogate";
	g->ext.callback = &gate_callback;
	g->ext.private_data = g;

	err = snd_pcm_extplug_create(&g->ext, name, root, slave, stream, mode);
	if (err < 0) {
		if (g->fd >= 0)
			close(g->fd);
		free(g);
		return err;
	}
	snd_pcm_extplug_set_param(&g->ext, SND_PCM_EXTPLUG_HW_FORMAT, SND_PCM_FORMAT_S16);
	snd_pcm_extplug_set_slave_param(&g->ext, SND_PCM_EXTPLUG_HW_FORMAT, SND_PCM_FORMAT_S16);

	*pcmp = g->ext.pcm;
	return 0;
}

SND_PCM_PLUGIN_SYMBOL(audiogate);
