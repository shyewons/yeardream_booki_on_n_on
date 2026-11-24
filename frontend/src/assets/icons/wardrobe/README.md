# 캐릭터 의상 공통 CSS 가이드

의상 적용 기준과 파일 목록은 이 문서 한 곳에서 관리합니다. 세트 폴더에는 착용 PNG만 두며, 별도 세트별 MD·catalog JSON·layers JSON은 만들지 않습니다. 필요한 파일명·부위·기본형 연결은 아래 표를 기준으로 프론트 코드나 DB에 연결합니다.

프론트 저장 위치는 `frontend/src/assets/icons/wardrobe/`입니다. DB의 `image_url`은 `/images/wardrobe/diary/...png`, `/images/wardrobe/story/...png` 등의 고정 경로를 유지하며, `src/wardrobeImages.js`의 `resolveWardrobeImage()`로 실제 이미지 URL에 연결합니다. `src/assets/` 파일을 DB 경로로 직접 요청하지 않습니다. 착용 참고 시안은 `frontend/design/mockups/wardrobe/`에 보관합니다.

## 1. 공통 캔버스와 기본형

- 모든 기본형·착용 PNG는 **1024×1536 투명 캔버스**, 같은 원점입니다. **투명 여백을 자르지 않습니다.**
- 기본형은 흰 밀착형 민소매·몸에 붙는 짧은 회색 반바지·맨발입니다. 얼굴·체형·다리를 모은 자세는 유지합니다.
- 기본형은 한 장만 표시합니다. 모자에 따라 아래 두 파일 중 하나를 사용합니다.

| 기본형 | 파일 | 적용 |
| --- | --- | --- |
| 기본 머리 포함 | [child-base.png](../../characters/child-base.png) | 모자 없음, 밀짚모자+긴 머리 |
| 머리 교체용 | [child-base-cap-compatible.png](../../characters/child-base-cap-compatible.png) | 파란 캡·동화 01~20의 모자/머리띠/고글/귀마개/머리핀/헬멧/리본/화관/두건+머리 |

머리 교체용 기본형은 기존 머리를 제거한 이미지입니다. 해당 모자·머리띠 PNG에 머리가 포함되어 있으므로 중복된 옆머리가 나오지 않게 함께 교체합니다. 머리 장식과 기본형이 둘 다 준비된 뒤 같은 렌더에서 바꿔 머리 없는 중간 상태가 보이지 않게 합니다. 모자 부위를 해제하면 기본 머리 포함 파일로 돌아갑니다.

## 2. CSS 배치와 겹침 순서

| 부위 | z-index |
| --- | --- |
| 기본형 | 0 |
| 하의 | 10 |
| 상의·한 벌 의상 | 20 |
| 모자+머리 | 30 |
| 신발 | 40 |
| 장갑·손 액세서리 | 50 |

```css
.avatar {
  position: relative;
  width: min(100%, 320px);
  aspect-ratio: 2 / 3;
  isolation: isolate;
}
.avatar > img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
  pointer-events: none;
}
.avatar__base { z-index: 0; }
.avatar__bottom { z-index: 10; }
.avatar__top { z-index: 20; }
.avatar__hat { z-index: 30; }
.avatar__shoes { z-index: 40; }
.avatar__accessory { z-index: 50; }
```

- 같은 부위는 한 번에 한 파일만 표시합니다. `gloves` 부위는 `.avatar__accessory`에 연결합니다.
- 기존 모자 부위에는 모자 외에도 헤어밴드·머리핀·고글·화관과 머리를 합친 PNG를 적용할 수 있습니다. 파일은 한 장으로 유지하고 z-index 30을 사용합니다. 얼굴과 체형을 성별 스타일마다 바꾸지 않습니다.
- 반응형 크기는 부모 `.avatar`만 조절합니다. 의상별 `transform`·별도 너비·높이·`object-position`·여백으로 위치를 바꾸지 않습니다.
- 모자+머리는 한 PNG로 함께 착용·해제합니다. 긴 머리는 상의 앞에 놓으며 앞·뒤 파일로 나누지 않습니다.
- 얼굴·귀·턱·목과 머리 안쪽의 경계는 실제 기본형 위에서 확인합니다. 캔버스가 같아도 배경이 보이는 틈이 생길 수 있습니다. 이때 기본형 이동·확대나 CSS 보정으로 맞추지 않고 머리 PNG의 투명 영역을 보정합니다. 밝고 어두운 배경 모두에서 확대 확인합니다.
- 양손 장갑과 한 켤레 신발도 각각 한 PNG·한 아이템입니다. 좌우 분리·복제·반전하지 않습니다.
- 장갑 부위는 손목밴드에 한정하지 않습니다. 주제에 따라 동물 발 장갑·벙어리장갑·손등 장식·팔찌 등으로 구성하되 동일한 전체 캔버스로 배치합니다.
- 피부에 가려지는 장화·장갑 입구 뒤쪽과 소매 안쪽은 PNG의 투명 영역입니다. CSS로 피부색을 덧칠하거나 이미지 위치를 바꿔 가리지 않습니다.
- 기본 옷·손가락·발끝이 겉옷 밖으로 보이거나 경계가 맞지 않으면 에셋 수정 대상입니다. 기본형 전체를 임의로 이동·확대하지 않습니다.
- 원본에 배경·외곽 발광·그림자를 추가하지 않습니다. 캐릭터 바닥 그림자는 필요할 때 부모 바깥의 CSS 장식으로 둡니다.
- 썸네일이 필요하면 별도 사본을 만듭니다. 착용용 원본은 자르지 않으며 `wardrobe-top-*.png` 같은 이전 카드 이미지를 착용 레이어로 쓰지 않습니다.

### 한 벌 의상 적용 규칙

사용자 결정에 따라 원피스·멜빵옷·우주복 등 상하의 한 벌도 제작 범위에 포함합니다. 아래는 적용 설계이며 앱 코드 변경이 완료되었다는 뜻은 아닙니다.

- 한 벌의 몸통과 하단은 하나의 PNG로 만들고 상의 레이어(z-index 20)에 표시합니다. 머리·신발·손 액세서리는 별도 부위로 유지합니다. 말하는 나무의 `outfit-layered-leaf-dress.png`, 별의 `outfit-starlight-cape-dress.png`, 장난감 기차의 `outfit-engineer-bib-overalls.png`도 한 벌 의상입니다.
- 한 벌 의상을 착용하는 동안 선택된 하의 레이어(z-index 10)를 숨깁니다. 기존 하의 선택은 기억해 두고 한 벌을 해제하면 다시 표시합니다. 기본형 전체를 숨기지 않습니다.
- 고양이 `outfit-cat-pinafore.png`, 토끼 `outfit-rabbit-gardener.png`, 바닷속 학교 `outfit-underwater-sailor-dress.png`, 장난감 로봇 `outfit-robot-mechanic-coverall.png`, 우주선 `outfit-ivory-space-suit.png`가 한 벌 의상입니다. 다른 상의·하의 PNG를 함께 겹치지 않습니다. `data-one-piece="true"`처럼 한 벌 착용 상태를 표시한다면 `.avatar[data-one-piece="true"] > .avatar__bottom { display: none; }`으로 하의만 숨길 수 있습니다.
- 기본형에 포함된 회색 반바지는 별도 레이어가 아니므로, 한 벌 PNG의 불투명 영역으로 가려져야 합니다. 투명한 치맛자락이나 지나치게 높은 옆트임으로 기본 옷이 노출되지 않게 제작합니다.
- 기존 부위별 옷과 한 벌을 구분하는 정보는 프론트 코드나 DB 연결에서 관리합니다. 이를 위해 별도 에셋 JSON을 만들지 않습니다.
- 한 벌 착용 중 다른 하의를 고르는 동작은 화면·기능 정의 단계에서 확정합니다. 의상 이미지 제작만으로 자동 해제·변경 동작까지 확정하지 않습니다.

## 3. 공용·일기 의상 파일

이 표의 경로는 현재 문서 기준입니다. 기존 `meadow-set` 의상은 일기 세트에서도 같은 파일을 재사용합니다.

| 부위 | 의상 | 파일 |
| --- | --- | --- |
| 모자 | 파란 캡+짧은 머리 | [diary/hat-blue-cap-short-hair.png](diary/hat-blue-cap-short-hair.png) |
| 모자 | 밀짚모자+긴 머리 | [meadow-set/01-hat-long-hair.png](meadow-set/01-hat-long-hair.png) |
| 상의 | 코랄 티셔츠 | [diary/top-coral-tshirt.png](diary/top-coral-tshirt.png) |
| 상의 | 초록 줄무늬 티셔츠 | [meadow-set/02-striped-shirt.png](meadow-set/02-striped-shirt.png) |
| 하의 | 노란 반바지 | [diary/bottom-yellow-shorts.png](diary/bottom-yellow-shorts.png) |
| 하의 | 청바지 | [diary/bottom-blue-jeans.png](diary/bottom-blue-jeans.png) |
| 하의 | 초록 치마 | [meadow-set/03-green-skirt.png](meadow-set/03-green-skirt.png) |
| 신발 | 초록 운동화 | [diary/shoes-green-sneakers.png](diary/shoes-green-sneakers.png) |
| 신발 | 노란 장화 | [meadow-set/04-yellow-boots.png](meadow-set/04-yellow-boots.png) |
| 장갑 부위 | 크림색 니트 손목밴드 | [diary/gloves-cream-knit-band.png](diary/gloves-cream-knit-band.png) |
| 장갑 부위 | 초록 천 팔찌 | [meadow-set/05-green-wristband.png](meadow-set/05-green-wristband.png) |

현재 두 손목 장식 파일은 모두 화면 오른쪽 손목에 맞춰져 있습니다. 다른 장갑 파일을 한쪽 손목 위치로 강제 배치하지 않습니다.

## 4. 동화 의상 파일

### 01-cat · 고양이

고양이 귀 머리띠·양갈래 머리와 원피스를 조합합니다. 얼굴·체형은 공통 기본형을 그대로 사용합니다.

| 부위 | 의상 | 파일 |
| --- | --- | --- |
| 모자 | 고양이 귀 머리띠+양갈래 머리 | [story/01-cat/hat-cat-earband-pigtails.png](story/01-cat/hat-cat-earband-pigtails.png) |
| 상의·한 벌 | 크림 블라우스+살구색 멜빵 원피스 | [story/01-cat/outfit-cat-pinafore.png](story/01-cat/outfit-cat-pinafore.png) |
| 장갑 | 양손 고양이 발 장갑 | [story/01-cat/gloves-cat-paws.png](story/01-cat/gloves-cat-paws.png) |

블라우스와 원피스는 한 PNG이며 상의 레이어(20)에 표시하고 하의 레이어는 숨깁니다. 머리띠와 머리는 상의 위(30), 양손 고양이 발 장갑은 액세서리 레이어(50)에 표시합니다. 기존 손목밴드와 장갑을 동시에 착용하지 않습니다. [실제 착용](../../../../design/mockups/wardrobe/story/01-cat-reward-composite.png)은 공용 노란 장화를 재사용합니다. 장화는 고양이 전용 보상 파일에 복제하지 않습니다.

### 02-dog · 강아지

| 부위 | 의상 | 파일 |
| --- | --- | --- |
| 모자 | 늘어진 강아지 귀 모자+짧은 머리 | [story/02-dog/hat-dog-ears-short-hair.png](story/02-dog/hat-dog-ears-short-hair.png) |
| 상의 | 파란 뼈다귀 무늬 상의 | [story/02-dog/top-dog-bone.png](story/02-dog/top-dog-bone.png) |
| 신발 | 강아지 얼굴 신발 한 켤레 | [story/02-dog/shoes-puppy.png](story/02-dog/shoes-puppy.png) |

신발 한 켤레가 한 PNG입니다. 고양이 세트와 달리 세 번째 의상은 신발이며, [실제 착용 합성본](../../../../design/mockups/wardrobe/story/02-dog-reward-composite.png)의 하의는 공용 노란 반바지를 사용합니다. 신발 입구 뒤쪽은 투명하게 두고, 기존 맨발의 발끝을 앞쪽 신발 이미지로 덮습니다.

### 03-rabbit · 토끼

| 부위 | 의상 | 파일 |
| --- | --- | --- |
| 모자 | 토끼 귀 리본+옆으로 땋은 머리 | [story/03-rabbit/hat-rabbit-ribbon-side-braid.png](story/03-rabbit/hat-rabbit-ribbon-side-braid.png) |
| 상의·한 벌 | 크림 셔츠+초록 멜빵 작업복 | [story/03-rabbit/outfit-rabbit-gardener.png](story/03-rabbit/outfit-rabbit-gardener.png) |
| 신발 | 당근 무늬 주황 장화 한 켤레 | [story/03-rabbit/shoes-carrot-boots.png](story/03-rabbit/shoes-carrot-boots.png) |

셔츠와 멜빵바지는 한 PNG이며 상의 레이어(20)에 표시하고 하의 레이어는 숨깁니다. 머리띠와 옆으로 땋은 머리는 상의 위(30)에 표시합니다. 작업복 바짓단은 장화보다 위에서 끝납니다. 장화는 한 켤레를 그대로 신발 레이어(40)에 표시합니다. [실제 착용 합성본](../../../../design/mockups/wardrobe/story/03-rabbit-reward-composite.png)을 기준으로 적용합니다.

### 04-dinosaur · 공룡

| 부위 | 의상 | 파일 |
| --- | --- | --- |
| 모자 | 탐험 고글+짧은 머리 | [story/04-dinosaur/hat-explorer-goggles-short-hair.png](story/04-dinosaur/hat-explorer-goggles-short-hair.png) |
| 상의 | 공룡 패치 탐험 재킷+안쪽 셔츠 | [story/04-dinosaur/top-dinosaur-field-jacket.png](story/04-dinosaur/top-dinosaur-field-jacket.png) |
| 하의 | 초록 카고 긴바지 | [story/04-dinosaur/bottom-forest-cargo-pants.png](story/04-dinosaur/bottom-forest-cargo-pants.png) |

재킷과 안쪽 셔츠는 상의 한 PNG입니다. 카고바지는 별도 하의 레이어(10), 재킷은 상의 레이어(20)에 표시합니다. 고글은 눈앞이 아닌 머리 위에 얹혀 있으며 머리와 함께 한 PNG로 교체합니다. [실제 착용 합성본](../../../../design/mockups/wardrobe/story/04-dinosaur-reward-composite.png)은 공용 초록 운동화를 재사용합니다.

### 05-little-dragon · 작은 용

| 부위 | 의상 | 파일 |
| --- | --- | --- |
| 모자 | 작은 뿔 머리띠+반묶음 머리 | [story/05-little-dragon/hat-dragon-horns-half-up-hair.png](story/05-little-dragon/hat-dragon-horns-half-up-hair.png) |
| 상의 | 짧은 보라 망토+비늘 조끼+안쪽 셔츠 | [story/05-little-dragon/top-dragon-cape-vest.png](story/05-little-dragon/top-dragon-cape-vest.png) |
| 장갑 부위 | 양손 비늘 손등 장식 | [story/05-little-dragon/gloves-dragon-scale-guards.png](story/05-little-dragon/gloves-dragon-scale-guards.png) |

망토·조끼·안쪽 셔츠는 상의 한 PNG입니다. 한 벌 의상이 아니므로 하의를 숨기지 않습니다. 망토는 어깨 주변에만 놓이고 팔 뒤에 가려질 면은 투명하게 처리합니다. 머리는 상의 위(30)에 표시합니다. 손등 장식은 손가락이 보이는 형태이며 양손을 한 PNG로 표시합니다. [실제 착용 합성본](../../../../design/mockups/wardrobe/story/05-little-dragon-reward-composite.png)은 공용 초록 치마·초록 운동화를 재사용합니다.

### 06-bear · 곰

| 부위 | 의상 | 파일 |
| --- | --- | --- |
| 모자 | 곰 귀 요리사 모자+짧은 머리 | [story/06-bear/hat-bear-chef-short-hair.png](story/06-bear/hat-bear-chef-short-hair.png) |
| 상의 | 크림 요리사 재킷+주황색 목수건 | [story/06-bear/top-bear-chef-jacket.png](story/06-bear/top-bear-chef-jacket.png) |
| 장갑 | 양손 곰 발 오븐 장갑 | [story/06-bear/gloves-bear-oven-mittens.png](story/06-bear/gloves-bear-oven-mittens.png) |

목수건은 재킷에 포함되어 상의 한 PNG로 표시합니다. 오븐 장갑은 손가락 전체를 덮으며, 손목 뒤에 가려지는 입구는 투명하게 처리합니다. 손목 장식과 중복해서 착용하지 않습니다. [실제 착용 합성본](../../../../design/mockups/wardrobe/story/06-bear-reward-composite.png)은 공용 청바지·초록 운동화를 재사용합니다.

### 07-penguin · 펭귄

| 부위 | 의상 | 파일 |
| --- | --- | --- |
| 모자 | 펭귄 귀마개+짧고 둥근 앞머리 | [story/07-penguin/hat-penguin-earmuffs-short-hair.png](story/07-penguin/hat-penguin-earmuffs-short-hair.png) |
| 상의 | 연미복+아이보리 셔츠+노란 나비넥타이 | [story/07-penguin/top-penguin-tailcoat.png](story/07-penguin/top-penguin-tailcoat.png) |
| 신발 | 짙은 회색 펭귄 신발 한 켤레 | [story/07-penguin/shoes-penguin-black.png](story/07-penguin/shoes-penguin-black.png) |

귀마개와 머리는 모자 부위 한 PNG입니다. 머리 스타일을 기존 옆가르마와 다르게 바꾸어도 기본형과 레이어 순서는 같습니다. 연미복·셔츠·나비넥타이는 상의 한 PNG이며 별도 하의를 유지합니다. [실제 착용 합성본](../../../../design/mockups/wardrobe/story/07-penguin-reward-composite.png)은 공용 청바지를 재사용합니다. 신발 한 켤레는 같은 원점에 표시하며, 바지나 발을 신발 이미지에 포함하지 않습니다.

### 08-underwater-school · 바닷속 학교

| 부위 | 의상 | 파일 |
| --- | --- | --- |
| 모자 | 조개 머리핀+긴 머리 | [story/08-underwater-school/hat-shell-clip-long-hair.png](story/08-underwater-school/hat-shell-clip-long-hair.png) |
| 상의·한 벌 | 하늘빛 세일러 원피스 | [story/08-underwater-school/outfit-underwater-sailor-dress.png](story/08-underwater-school/outfit-underwater-sailor-dress.png) |
| 신발 | 조개 장식 메리제인 신발 한 켤레 | [story/08-underwater-school/shoes-shell-mary-janes.png](story/08-underwater-school/shoes-shell-mary-janes.png) |

원피스는 상의 레이어(20)에 표시하고 별도 하의 레이어는 숨깁니다. 기본형의 회색 반바지는 원피스 자체로 덮습니다. 조개 머리핀과 긴 머리는 한 PNG로 교체합니다. 신발의 발등이 드러나는 구간에는 피부를 그리지 않고 기본형이 보이도록 투명하게 둡니다. [실제 착용 합성본](../../../../design/mockups/wardrobe/story/08-underwater-school-reward-composite.png)을 기준으로 적용합니다.

### 09-squirrel · 다람쥐

| 부위 | 의상 | 파일 |
| --- | --- | --- |
| 모자 | 도토리 베레모+낮게 땋은 머리 | [story/09-squirrel/hat-acorn-beret-low-braids.png](story/09-squirrel/hat-acorn-beret-low-braids.png) |
| 상의 | 조끼+크림 셔츠+우편 가방 | [story/09-squirrel/top-squirrel-mail-vest.png](story/09-squirrel/top-squirrel-mail-vest.png) |
| 하의 | 모래색 카고 칠부바지 | [story/09-squirrel/bottom-sand-cropped-cargo.png](story/09-squirrel/bottom-sand-cropped-cargo.png) |

셔츠·조끼·가방·가방 끈은 상의 한 PNG로 함께 착용합니다. 가방 부위를 따로 추가하지 않습니다. 바지는 별도 하의 레이어(10), 상의는 20, 베레모와 머리는 30에 표시합니다. 낮게 땋은 머리는 상의 앞에 놓습니다. [실제 착용 합성본](../../../../design/mockups/wardrobe/story/09-squirrel-reward-composite.png)은 공용 초록 운동화를 재사용합니다.

### 10-dokkaebi · 도깨비

| 부위 | 의상 | 파일 |
| --- | --- | --- |
| 모자 | 작은 도깨비 뿔 머리띠+짧은 웨이브 머리 | [story/10-dokkaebi/hat-dokkaebi-horns-wavy-crop.png](story/10-dokkaebi/hat-dokkaebi-horns-wavy-crop.png) |
| 상의 | 청록색 한복 저고리+고름 | [story/10-dokkaebi/top-dokkaebi-hanbok-jacket.png](story/10-dokkaebi/top-dokkaebi-hanbok-jacket.png) |
| 하의 | 황토색 한복 바지 | [story/10-dokkaebi/bottom-dokkaebi-ochre-baji.png](story/10-dokkaebi/bottom-dokkaebi-ochre-baji.png) |

고름은 상의 한 PNG에 포함합니다. 바지(10)·저고리(20)·머리띠+머리(30)는 별도 레이어이며 하의를 숨기지 않습니다. 얼굴을 도깨비로 바꾸지 않고 같은 기본형을 사용합니다. [실제 착용 합성본](../../../../design/mockups/wardrobe/story/10-dokkaebi-reward-composite.png)은 공용 초록 운동화를 재사용합니다.

### 11-toy-robot · 장난감 로봇

| 부위 | 의상 | 파일 |
| --- | --- | --- |
| 모자 | 정비 고글+높게 묶은 옆 포니테일 | [story/11-toy-robot/hat-robot-goggles-high-ponytail.png](story/11-toy-robot/hat-robot-goggles-high-ponytail.png) |
| 상의·한 벌 | 로봇 패치 정비 작업복 | [story/11-toy-robot/outfit-robot-mechanic-coverall.png](story/11-toy-robot/outfit-robot-mechanic-coverall.png) |
| 장갑 | 양손 장난감 로봇 장갑 | [story/11-toy-robot/gloves-toy-robot-hands.png](story/11-toy-robot/gloves-toy-robot-hands.png) |

정비복의 상·하의는 한 PNG로 상의 레이어(20)에 표시하고 별도 하의를 숨깁니다. 고글은 이마 위에 두며 포니테일과 한 PNG(30)로 사용합니다. 양손 로봇 장갑은 액세서리 레이어(50)에 표시합니다. 캐릭터의 팔·손 자세를 바꾸거나 장갑을 좌우 반전하지 않습니다. [실제 착용 합성본](../../../../design/mockups/wardrobe/story/11-toy-robot-reward-composite.png)은 공용 초록 운동화를 사용합니다.

### 12-spaceship · 우주선

| 부위 | 의상 | 파일 |
| --- | --- | --- |
| 모자 | 얼굴이 보이는 우주 헬멧+짧은 앞머리 | [story/12-spaceship/hat-space-helmet-short-fringe.png](story/12-spaceship/hat-space-helmet-short-fringe.png) |
| 상의·한 벌 | 아이보리 우주복 | [story/12-spaceship/outfit-ivory-space-suit.png](story/12-spaceship/outfit-ivory-space-suit.png) |
| 신발 | 아이보리 우주 신발 한 켤레 | [story/12-spaceship/shoes-ivory-space-boots.png](story/12-spaceship/shoes-ivory-space-boots.png) |

우주복은 상의 레이어(20)에 표시하고 별도 하의를 숨깁니다. 헬멧과 짧은 머리는 한 PNG(30)입니다. 얼굴이 보이는 구간은 투명하며 별도 유리 레이어를 추가하지 않습니다. 신발 한 켤레는 신발 레이어(40)에 표시합니다. [실제 착용 합성본](../../../../design/mockups/wardrobe/story/12-spaceship-reward-composite.png)을 기준으로 적용합니다.

### 13-magic-bag · 마법 가방

| 부위 | 의상 | 파일 |
| --- | --- | --- |
| 모자 | 별 리본+반묶음 머리 | [story/13-magic-bag/hat-ribbon-half-up-hair.png](story/13-magic-bag/hat-ribbon-half-up-hair.png) |
| 상의 | 보라색 포켓 코트+마법 가방 | [story/13-magic-bag/top-magic-pocket-coat-bag.png](story/13-magic-bag/top-magic-pocket-coat-bag.png) |
| 장갑 | 양손 별 장갑 | [story/13-magic-bag/gloves-gold-star.png](story/13-magic-bag/gloves-gold-star.png) |

코트·안쪽 셔츠·짧은 망토·가방·가방 끈은 상의 한 PNG(20)입니다. 별도 가방 부위를 추가하지 않습니다. 한 벌 의상이 아니므로 하의는 유지합니다. 리본과 반묶음 머리는 한 PNG(30), 양손 장갑은 한 PNG(50)로 표시합니다. [실제 착용 합성본](../../../../design/mockups/wardrobe/story/13-magic-bag-reward-composite.png)은 공용 초록 치마·초록 운동화를 재사용합니다.

### 14-secret-door · 비밀 문

| 부위 | 의상 | 파일 |
| --- | --- | --- |
| 모자 | 탐정 모자+짧은 옆가르마 머리 | [story/14-secret-door/hat-detective-cap-short-hair.png](story/14-secret-door/hat-detective-cap-short-hair.png) |
| 상의 | 베이지 탐정 트렌치코트 | [story/14-secret-door/top-detective-trench-coat.png](story/14-secret-door/top-detective-trench-coat.png) |
| 하의 | 갈색 체크 바지 | [story/14-secret-door/bottom-detective-check-trousers.png](story/14-secret-door/bottom-detective-check-trousers.png) |

트렌치코트와 안쪽 셔츠·벨트는 상의 한 PNG(20)이며 체크 바지는 하의(10)로 따로 표시합니다. 모자와 짧은 머리는 한 PNG(30)입니다. 코트를 입어도 하의를 숨기지 않습니다. [실제 착용 합성본](../../../../design/mockups/wardrobe/story/14-secret-door-reward-composite.png)은 공용 초록 운동화를 재사용합니다.

### 15-talking-tree · 말하는 나무

| 부위 | 의상 | 파일 |
| --- | --- | --- |
| 모자 | 나뭇잎 화관+긴 머리 | [story/15-talking-tree/hat-leaf-crown-long-hair.png](story/15-talking-tree/hat-leaf-crown-long-hair.png) |
| 상의·한 벌 | 나뭇잎을 겹친 원피스 | [story/15-talking-tree/outfit-layered-leaf-dress.png](story/15-talking-tree/outfit-layered-leaf-dress.png) |
| 장갑 부위 | 양손 나뭇잎 손등 장식 | [story/15-talking-tree/gloves-leaf-hand-ornaments.png](story/15-talking-tree/gloves-leaf-hand-ornaments.png) |

블라우스·몸통·치마는 한 벌 PNG(20)로 표시하며 별도 하의(10)는 숨깁니다. 화관과 긴 머리는 한 PNG(30)로 상의 앞에 놓습니다. 손등 장식은 한 PNG(50)이며 손가락이 보이는 영역은 투명하게 둡니다. [실제 착용 합성본](../../../../design/mockups/wardrobe/story/15-talking-tree-reward-composite.png)은 공용 초록 운동화를 재사용합니다.

### 16-cloud-village · 구름 마을

| 부위 | 의상 | 파일 |
| --- | --- | --- |
| 모자 | 구름 무늬 두건+가벼운 짧은 머리 | [story/16-cloud-village/hat-cloud-bandana-soft-crop.png](story/16-cloud-village/hat-cloud-bandana-soft-crop.png) |
| 상의 | 구름 주머니 조끼+크림 셔츠 | [story/16-cloud-village/top-cloud-vest-shirt.png](story/16-cloud-village/top-cloud-vest-shirt.png) |
| 하의 | 하늘빛 벌룬 바지 | [story/16-cloud-village/bottom-cloud-balloon-trousers.png](story/16-cloud-village/bottom-cloud-balloon-trousers.png) |

두건과 짧은 머리는 한 PNG(30)입니다. 셔츠와 조끼는 상의 한 PNG(20), 바지는 별도 하의(10)로 표시합니다. [실제 착용 합성본](../../../../design/mockups/wardrobe/story/16-cloud-village-reward-composite.png)은 공용 초록 운동화를 사용합니다.

### 17-returning-star · 집으로 돌아가는 별

| 부위 | 의상 | 파일 |
| --- | --- | --- |
| 모자 | 별 머리핀+어깨 길이 웨이브 머리 | [story/17-returning-star/hat-star-clip-soft-waves.png](story/17-returning-star/hat-star-clip-soft-waves.png) |
| 상의·한 벌 | 별 장식 케이프 원피스 | [story/17-returning-star/outfit-starlight-cape-dress.png](story/17-returning-star/outfit-starlight-cape-dress.png) |
| 신발 | 달 장식 메리제인 | [story/17-returning-star/shoes-moon-mary-janes.png](story/17-returning-star/shoes-moon-mary-janes.png) |

짧은 케이프·소매·원피스는 한 벌 PNG(20)로 표시하며 기존 하의(10)는 숨깁니다. 머리핀과 머리는 한 PNG(30), 신발 한 켤레는 한 PNG(40)입니다. 신발의 발등 구멍은 투명하게 두어 기본형의 피부가 보이게 합니다. [실제 착용 합성본](../../../../design/mockups/wardrobe/story/17-returning-star-reward-composite.png)을 기준으로 적용합니다.

### 18-flying-shoes · 하늘을 나는 신발

| 부위 | 의상 | 파일 |
| --- | --- | --- |
| 모자 | 날개 머리띠+부드러운 짧은 앞머리 | [story/18-flying-shoes/hat-wing-headband-textured-fringe.png](story/18-flying-shoes/hat-wing-headband-textured-fringe.png) |
| 상의 | 주황 바람막이+안쪽 티셔츠 | [story/18-flying-shoes/top-orange-windbreaker.png](story/18-flying-shoes/top-orange-windbreaker.png) |
| 신발 | 날개 장식 주황 운동화 | [story/18-flying-shoes/shoes-winged-orange-sneakers.png](story/18-flying-shoes/shoes-winged-orange-sneakers.png) |

머리띠와 짧은 머리는 한 PNG(30)이며 구름 마을의 이마가 드러나는 머리와 구분합니다. 바람막이·안쪽 티셔츠는 상의 한 PNG(20), 날개와 신발 한 켤레는 신발 한 PNG(40)입니다. 날개를 별도 레이어로 나누지 않습니다. [실제 착용 합성본](../../../../design/mockups/wardrobe/story/18-flying-shoes-reward-composite.png)은 공용 청바지를 사용하며 하의를 숨기지 않습니다.

### 19-snowman · 눈사람

| 부위 | 의상 | 파일 |
| --- | --- | --- |
| 모자 | 눈송이 귀마개+옆으로 땋은 머리 | [story/19-snowman/hat-snow-earmuffs-side-braid.png](story/19-snowman/hat-snow-earmuffs-side-braid.png) |
| 상의 | 눈사람 장식 분홍 겨울 코트 | [story/19-snowman/top-rose-winter-coat.png](story/19-snowman/top-rose-winter-coat.png) |
| 장갑 | 양손 눈송이 벙어리장갑 | [story/19-snowman/gloves-snowflake-mittens.png](story/19-snowman/gloves-snowflake-mittens.png) |

귀마개와 땋은 머리는 한 PNG(30)이며 상의 앞에 놓습니다. 코트·안쪽 니트 목깃은 상의 한 PNG(20)로 표시하고 별도 하의를 유지합니다. 양손 장갑은 한 PNG(50)로 손가락을 덮습니다. [실제 착용 합성본](../../../../design/mockups/wardrobe/story/19-snowman-reward-composite.png)은 공용 청바지·초록 운동화를 사용합니다. 목깃과 얼굴 경계 보정은 PNG에 반영했으며 CSS에서 위치를 옮기지 않습니다.

### 20-toy-train · 장난감 기차

| 부위 | 의상 | 파일 |
| --- | --- | --- |
| 모자 | 기관사 모자+부드러운 짧은 옆가르마 | [story/20-toy-train/hat-engineer-cap-soft-short-hair.png](story/20-toy-train/hat-engineer-cap-soft-short-hair.png) |
| 상의·한 벌 | 크림 셔츠+남색 멜빵 작업복 | [story/20-toy-train/outfit-engineer-bib-overalls.png](story/20-toy-train/outfit-engineer-bib-overalls.png) |
| 신발 | 갈색 작업화 한 켤레 | [story/20-toy-train/shoes-brown-work-boots.png](story/20-toy-train/shoes-brown-work-boots.png) |

셔츠·목수건·멜빵바지는 한 벌 PNG(20)로 표시하고 선택된 하의(10)는 숨깁니다. 모자와 짧은 머리는 한 PNG(30), 작업화 한 켤레는 한 PNG(40)입니다. 신발 뒤쪽 테두리는 투명하게 처리하고 바짓단은 신발과 겹쳐도 옆으로 튀어나오지 않도록 조정했습니다. [실제 착용 합성본](../../../../design/mockups/wardrobe/story/20-toy-train-reward-composite.png)을 기준으로 적용합니다.

## 5. 실제 합성 확인과 남은 조합

- 서비스에는 합성본이 아닌 기본형과 부위별 PNG를 적용합니다. 실제 합성본은 이미지 정렬을 확인하는 참고용입니다.
- [동화 01~03 실제 착용 비교](../../../../design/mockups/wardrobe/story/batch-01-03-comparison.png)는 같은 기본형·원점으로 분리 PNG를 겹친 결과입니다. 고양이·토끼의 한 벌 조합에서는 별도 하의를 숨깁니다.
- [동화 04~06 실제 착용 비교](../../../../design/mockups/wardrobe/story/batch-04-06-comparison.png)는 공룡 탐험가·작은 용·곰 요리사 조합입니다. 세 조합 모두 상의와 하의를 별도 레이어로 표시합니다.
- [동화 07~09 실제 착용 비교](../../../../design/mockups/wardrobe/story/batch-07-09-comparison.png)는 펭귄 연미복·바닷속 학교·다람쥐 우편배달부 조합입니다. 바닷속 학교만 한 벌 의상으로 별도 하의를 숨깁니다.
- [동화 10~12 실제 착용 비교](../../../../design/mockups/wardrobe/story/batch-10-12-comparison.png)는 도깨비 한복·장난감 로봇 정비복·우주복 조합입니다. 로봇 정비복과 우주복은 한 벌 의상으로 별도 하의를 숨깁니다.
- [동화 13~15 실제 착용 비교](../../../../design/mockups/wardrobe/story/batch-13-15-comparison.png)는 마법 가방 코트·비밀 문 탐정·말하는 나무 원피스 조합입니다. 나무 원피스만 한 벌 의상으로 별도 하의를 숨기며, 두 코트는 하의를 함께 표시합니다.
- [동화 16~18 실제 착용 비교](../../../../design/mockups/wardrobe/story/batch-16-18-comparison.png)는 구름 마을·집으로 돌아가는 별·하늘을 나는 신발 조합입니다. 별 케이프 원피스는 한 벌 의상으로 하의를 숨기고, 구름 조끼와 주황 바람막이는 별도 하의와 함께 표시합니다.
- [동화 19~20 실제 착용 비교](../../../../design/mockups/wardrobe/story/batch-19-20-comparison.png)는 눈사람 겨울 코트·장난감 기차 기관사 조합입니다. 코트는 공용 청바지와 함께 표시하고, 기관사 멜빵 작업복은 한 벌 의상으로 별도 하의를 숨깁니다. 기본형·6개 부위별 PNG를 같은 원점에 겹쳐 확인했습니다.
- [기본형과 기존 착용 조합](../../../../design/mockups/wardrobe/13-fitted-base-and-outfits.png), [일기 상의·하의 6조합](../../../../design/mockups/wardrobe/09-diary-tops-bottoms.png), [일기 전체 착용](../../../../design/mockups/wardrobe/10-diary-accessories-outfits.png)을 참고합니다.
- **청바지+노란 장화:** 기존 청바지 밑단이 장화 옆으로 나옵니다. z-index만으로 해결되지 않는 에셋 조합 문제이며 별도 보정이 필요합니다. 현재 검토본에서는 청바지를 운동화와, 장화를 치마와 조합했습니다.
- 각 세트의 검토본에 없는 조합은 추가 확인이 필요합니다. 새 의상은 같은 원점으로 실제 PNG를 겹쳐 목선·소매·허리·머리 끝·손목·신발 입구를 확인합니다.
