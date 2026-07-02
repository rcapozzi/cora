from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cora', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                -- Drop trigger and function first (idempotent)
                DROP TRIGGER IF EXISTS t_label_images_to_queue ON label_images;
                DROP FUNCTION IF EXISTS trigger_send_to_pgmq();
            """,
            reverse_sql="""
                DROP TRIGGER IF EXISTS t_label_images_to_queue ON label_images;
                DROP FUNCTION IF EXISTS trigger_send_to_pgmq();
            """,
        ),
        migrations.RunSQL(
            sql="""
                CREATE EXTENSION IF NOT EXISTS pgmq CASCADE;
                -- Create queue if it doesn't exist
                SELECT pgmq.create('q_label_images');
            """,
            reverse_sql="SELECT pgmq.drop_queue('q_label_images');",
        ),
        migrations.RunSQL(
            sql="""
                -- Create trigger function
                CREATE OR REPLACE FUNCTION trigger_send_to_pgmq()
                RETURNS TRIGGER AS $$
                BEGIN
                    PERFORM pgmq.send(
                        'q_label_images', 
                        jsonb_build_object('id', NEW.id, 'file_path', NEW.file_path, 'file_name', NEW.file_name)
                    );
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
            """,
            reverse_sql="DROP FUNCTION IF EXISTS trigger_send_to_pgmq();",
        ),
        migrations.RunSQL(
            sql="""
                -- Bind trigger to table
                CREATE TRIGGER t_label_images_to_queue
                AFTER INSERT ON label_images
                FOR EACH ROW
                EXECUTE FUNCTION trigger_send_to_pgmq();
            """,
            reverse_sql="DROP TRIGGER IF EXISTS t_label_images_to_queue ON label_images;",
        ),
    ]
    