import asyncio
import logging
import threading
import time

logger = logging.getLogger(__name__)

# Try to import libtorrent, but make it optional
try:
    import libtorrent as lt
    LIBTORRENT_AVAILABLE = True
except ImportError:
    logger.warning("libtorrent not available, DHT service will be disabled")
    LIBTORRENT_AVAILABLE = False
    lt = None


class DHTService:
    def __init__(self):
        self.session = None
        self.thread = None
        self.available = LIBTORRENT_AVAILABLE

    def start(self):
        if not self.available:
            logger.info("DHT service not available (libtorrent not installed)")
            return
        
        if self.session:
            return

        self.session = lt.session({
            'listen_interfaces': '0.0.0.0:6881,[::]:6881',
            'dht_bootstrap_nodes': 'router.utorrent.com:6881,router.bittorrent.com:6881,dht.transmissionbt.com:6881'
        })

        self.thread = threading.Thread(target=self._run_service)
        self.thread.daemon = True
        self.thread.start()
        logger.info("DHT service started")

    def _run_service(self):
        while self.session:
            self.session.post_dht_stats()
            time.sleep(1)

    def stop(self):
        if self.session:
            self.session = None
            if self.thread:
                self.thread.join()
            logger.info("DHT service stopped")

    async def get_torrent_file(self, magnet_link: str) -> bytes | None:
        if not self.available:
            logger.warning("DHT service not available, cannot get torrent file")
            return None
        
        if not self.session:
            raise RuntimeError("DHT service not started")

        params = lt.parse_magnet_uri(magnet_link)
        # Add trackers from magnet link
        if params.trackers:
            for tracker in params.trackers:
                params.trackers.append(tracker)
        params.save_path = '.'
        params.storage_mode = lt.storage_mode_t.storage_mode_sparse
        handle = self.session.add_torrent(params)

        for _ in range(60):
            if handle.status().has_metadata:
                torrent_info = handle.get_torrent_info()
                if torrent_info:
                    torrent_file = lt.create_torrent(torrent_info)
                    self.session.remove_torrent(handle)
                    return lt.bencode(torrent_file.generate())
            await asyncio.sleep(1)

        self.session.remove_torrent(handle)
        logger.warning(f"Timeout while fetching metadata for {magnet_link}")
        return None


dht_service = DHTService()
