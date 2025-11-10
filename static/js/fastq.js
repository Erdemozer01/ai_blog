// JavaScript konfigürasyonu (template veya static file'da)
Resumable({
    target: '/bio-tools/fastq-analyzer/API/resumable',
    chunkSize: 5 * 1024 * 1024,  // 5 MB
    simultaneousUploads: 3,
    testChunks: false
});