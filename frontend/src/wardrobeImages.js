const wardrobeImages = import.meta.glob('./assets/icons/wardrobe/**/*.png', {
    eager: true,
    query: '?url',
    import: 'default',
})

export const wardrobeImagePaths = new Set(Object.keys(wardrobeImages).map((path) => path.replace('./assets/icons/wardrobe/', '')))

// DB의 고정 경로를 빌드 시 생성되는 이미지 URL로 연결한다.
export function resolveWardrobeImage(imageUrl) {
    const prefix = '/images/wardrobe/'
    if (typeof imageUrl !== 'string' || !imageUrl.startsWith(prefix)) return imageUrl

    const assetPath = './assets/icons/wardrobe/' + imageUrl.slice(prefix.length)
    return wardrobeImages[assetPath] || imageUrl
}
