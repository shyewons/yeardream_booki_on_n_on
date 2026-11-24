import assert from 'node:assert/strict'
import test from 'node:test'
import { readdirSync, readFileSync } from 'node:fs'
import { getAvatarAppearance, describeWardrobeImage } from '../src/wardrobeAppearance.js'
import { wardrobeImageBounds } from '../src/wardrobeImageBounds.js'

const prefix = '/images/wardrobe/'
const clothes = (path, id = 1) => ({ id, name: path, image_url: prefix + path })
const paths = new Set([
    'diary/hat-blue-cap-short-hair.png',
    'diary/top-coral-tshirt.png',
    'diary/bottom-yellow-shorts.png',
    'meadow-set/01-hat-long-hair.png',
    'story/01-cat/outfit-cat-pinafore.png',
    'story/01-cat/hat-cat-earband-pigtails.png',
    'story/01-cat/gloves-cat-paws.png',
])

test('빈 옷장은 기본 머리가 있는 캐릭터를 표시한다', () => {
    assert.deepEqual(getAvatarAppearance({}, paths), { base: 'regular', layers: [], hiddenBottom: false })
})

test('모자와 머리는 함께 교체하고 해제하면 기본 머리로 돌아간다', () => {
    const character = { hat: clothes('diary/hat-blue-cap-short-hair.png') }
    assert.equal(getAvatarAppearance(character, paths).base, 'cap-compatible')
    assert.equal(getAvatarAppearance({ ...character, hat: null }, paths).base, 'regular')
    assert.equal(getAvatarAppearance({ hat: clothes('meadow-set/01-hat-long-hair.png') }, paths).base, 'regular')
})

test('한 벌은 하의를 숨기고 벗으면 저장된 하의를 다시 표시한다', () => {
    const bottom = clothes('diary/bottom-yellow-shorts.png', 2)
    const character = { bottom, top: clothes('story/01-cat/outfit-cat-pinafore.png', 3) }
    const appearance = getAvatarAppearance(character, paths)
    assert.equal(appearance.hiddenBottom, true)
    assert.deepEqual(appearance.layers.map((layer) => layer.slot), ['top'])
    assert.equal(character.bottom, bottom)
    assert.deepEqual(getAvatarAppearance({ ...character, top: null }, paths).layers.map((layer) => layer.slot), ['bottom'])
})

test('일반 옷은 하의, 상의, 머리, 장갑 순서로 겹친다', () => {
    const appearance = getAvatarAppearance({
        gloves: clothes('story/01-cat/gloves-cat-paws.png'),
        hat: clothes('story/01-cat/hat-cat-earband-pigtails.png'),
        top: clothes('diary/top-coral-tshirt.png'),
        bottom: clothes('diary/bottom-yellow-shorts.png'),
    }, paths)
    assert.deepEqual(appearance.layers.map((layer) => layer.slot), ['bottom', 'top', 'hat', 'gloves'])
    assert.deepEqual(appearance.layers.map((layer) => layer.zIndex), [10, 20, 30, 50])
})

test('로드하지 못한 모자와 한 벌 때문에 머리나 하의를 숨기지 않는다', () => {
    const character = {
        hat: clothes('story/01-cat/hat-cat-earband-pigtails.png'),
        top: clothes('story/01-cat/outfit-cat-pinafore.png'),
        bottom: clothes('diary/bottom-yellow-shorts.png'),
    }
    const appearance = getAvatarAppearance(character, new Set(['diary/bottom-yellow-shorts.png']))
    assert.equal(appearance.base, 'regular')
    assert.equal(appearance.hiddenBottom, false)
    assert.deepEqual(appearance.layers.map((layer) => layer.slot), ['bottom'])
})

test('이전 썸네일, 외부 URL, 잘못된 부위 이미지는 착용 레이어로 사용하지 않는다', () => {
    assert.equal(describeWardrobeImage('/assets/wardrobe-top-blue.png'), null)
    assert.equal(describeWardrobeImage('https://example.com/hat.png'), null)
    assert.equal(describeWardrobeImage(prefix + '../characters/child-base.png'), null)
    assert.deepEqual(getAvatarAppearance({ top: clothes('diary/bottom-yellow-shorts.png') }, paths).layers, [])
})

test('등록된 의상 전체가 공통 캔버스와 유효한 카드 표시 범위를 가진다', () => {
    const directory = new URL('../src/assets/icons/wardrobe/', import.meta.url)
    const files = readdirSync(directory, { recursive: true }).filter((path) => path.endsWith('.png')).map((path) => path.replaceAll('\\', '/'))
    assert.equal(files.length, 71)
    assert.deepEqual(Object.keys(wardrobeImageBounds).sort(), files.sort())
    let onePieces = 0
    for (const path of files) {
        const image = describeWardrobeImage(prefix + path)
        assert.ok(image, path)
        if (image.onePiece) onePieces += 1
        const buffer = readFileSync(new URL(path, directory))
        assert.equal(buffer.readUInt32BE(16), 1024, path)
        assert.equal(buffer.readUInt32BE(20), 1536, path)
        const [x, y, width, height] = wardrobeImageBounds[path]
        assert.ok(x >= 0 && y >= 0 && width > 0 && height > 0 && x + width <= 1024 && y + height <= 1536, path)
    }
    assert.equal(onePieces, 8)
})
