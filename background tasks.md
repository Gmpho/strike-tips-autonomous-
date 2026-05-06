light task and heavy tasks 

will use celery and redis que with celery worker 
after tasks execution send respond to DB or setup with redis sever as we already have it with our agent bot for real time update and notifications with telegram bot api 

will setup task scheduler for the tasks as we already have cron jobs for tasks  they will api that fetches this data and insert/update into DB or redis for now this is what we have 
will test this and then create proper task scheduler with celery and redis que with celery worker to make it scalable and reliable  the more tasks we add this will not support the load so we need celery and redis que with celery worker uhmmm also this real updates can be agent reasearching analysying markets pdfs etc.. 



so the 6379 so that we can use the localhost:6379 in our fastapi application also we need to setup the celery app in fast api  we are not going to spin up the celery cotainer this must use the logic which is present in our local machine  the tasks will be triggered from the fastapi application  the workers must be running in background setup celery app in fastapi  and 6379 is for caching and task que we already have 6379 running on my local machine for our agent bot and it is working fine as far as the caching is concerned  uhmmm for the task que and celery app i am not sure how this is going to work on my local machine so i need you to setup the task que and celery app in fast api   we can use the localhost:6379 for the task que and celery app also or we can use a different port for the task que and celery app  i am not sure what is best so i leave it up to you 

uhmmm second then we create the synchronous celery task process cause the api betway uses async ... so uhmmm will create a synchronous celery task process 
will asl create a api to use task process 
then we intergrate it with fastapi main py our main application or is it api.py 
also a seperate router for this celery task and the celery will be intergrated 
will then start the cotainer 
then we test it 

then we use our exsisting configs 

so i believe we can do this without breaking 



worker.py

from celery import celery 

celery_app = celery 
 worker 
 broker redis localhost 6379/0
 backend redis localhost 6379/0

so celery will be the one to pick the task from redis message que
it will check for the broker for task task from yhe 
