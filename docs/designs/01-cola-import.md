# COLA Import
Record enter `CORA` though a message broker. A message client listens on the queue. The message includes a label image along with values from `COLA` entered by the Applicant. 
The message client performs OCR on the image.
Finally, the message is inserted into Postgres by calling `CORA` `import-cola`

```mermaid
sequenceDiagram
    participant A as COLA
    participant Q as Message Broker/Queue
    participant C as Message Client
    participant O as CORA
    participant P as PostgreSQL

    A->>Q: Submit label image + COLA fields
    Q-->>C: Queue message
    C->>C: Perform OCR on image
    C->>O: POST import-cola
    O->>P: Insert record
    P-->>O: Record saved
    O-->>C: 200
```


# Specialist Review

* The Specialist start by getting a list of application that have been OCR-ed, but not reviewed.
* CORA return a pageable list of applications 'ready for review'.
* The Specialist selects an item.
* CORA updates Postgress for that application to change status in 'in review'.
* The Specialist reviews the item and approves/rejects the application.
* CORA update the application status in the database.
* CORA sends a message to the broker.


NOTE: Interaction between Message Broker and Cola are ommitted for brevity.
```mermaid
sequenceDiagram
    participant S as Specialist
    participant CORA
    participant P as Postgres
    participant Q as Message Broker/Queue

    S ->> CORA: List applications (OCR data availible)
    CORA -->> S:

    S ->> CORA: Get application (application id)
    CORA ->> P: Status in-review where status is ready-for-review
    P -->> CORA: OK (Error can occur due to status change)
    CORA -->> S: Application details

    S ->> CORA: Update application (application id accept/reject)
    CORA ->> P: Status change to accept/reject
    CORA ->> Q: status_change (use Claim Check Strategy)
    Q -->> CORA: ACK
    CORA -->> S: 200

```
