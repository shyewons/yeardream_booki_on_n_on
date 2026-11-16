# -*- coding: utf-8 -*-
"""그래프 노드. 파일 1개 = 노드 1개.
모든 노드는 State(state.py)를 받아 자기가 만든 키만 dict로 돌려준다. 이 약속만 지키면 파일 안을 바꿔도 다른 노드에 영향이 없다.

  노드                 읽는 키                                              쓰는 키
  spell_correct        original_sentence                                     revised_sentence
  extract_diff         original_sentence, revised_sentence                   difference
  compliment           (없음)                                                compliment
  rewrite_queries      difference                                            rewritten_queries
  retrieve_evidence    rewritten_queries                                     evidence_docs
  explain              difference, rewritten_queries, evidence_docs          explanations
  build_response       유효성 검사 키 전체 + 위 키 전체                       response
"""
