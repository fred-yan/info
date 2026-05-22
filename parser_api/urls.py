from django.urls import path
from . import views
from . import frontend_views

urlpatterns = [
    path("economist/", views.economist_view),
    path("apnews/", views.apnews_view),
    path("ftchinese/", views.ftchinese_view),
    path("cn_wsj/", views.wsj_view),
    path("kr36/", views.kr36_view),
    path("huxiu/", views.huxiu_view),
    path("wst_post/", views.wst_post_view),
    path("zaobao/", views.zaobao_view),
    path("github/trending", views.github_trending_view),
    path("zaobao/hotlist/", views.zaobao_hotlist_view),
    path("hacker_news/topstories/", views.hacker_news_top_stories_view),
    path("zhihu/", views.zhihu_view),
    path("pengpai/", views.pengpai_view),
    path("weibo/", views.weibo_view),
    path("scheduler/status/", views.scheduler_status_view),
    path("keywords/", views.keywords_view),
    path("keywords/llm/", views.llm_keywords_view),
    # Frontend API endpoints
    path("keywords/ranking/", frontend_views.keywords_ranking_view),
    path("keywords/trend/", frontend_views.keywords_trend_view),
    path("keywords/articles/", frontend_views.keywords_articles_view),
    path("news/feed/", frontend_views.news_feed_view),
    path("platforms/", frontend_views.platforms_view),
]
