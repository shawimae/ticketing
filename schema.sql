-- MySQL dump 10.13  Distrib 8.0.43, for macos15 (x86_64)
--
-- Host: localhost    Database: ticketing_db
-- ------------------------------------------------------
-- Server version	9.4.0

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `entries`
--

DROP TABLE IF EXISTS `entries`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `entries` (
  `ticket_no` int NOT NULL AUTO_INCREMENT,
  `store_name` varchar(45) DEFAULT NULL,
  `contact_number` varchar(45) DEFAULT NULL,
  `subject` varchar(45) DEFAULT NULL,
  `assigned_it` varchar(255) DEFAULT NULL,
  `date` datetime DEFAULT NULL,
  `email` varchar(255) DEFAULT NULL,
  `concern` varchar(255) DEFAULT NULL,
  `status` varchar(50) NOT NULL DEFAULT 'pending',
  `remedy` varchar(255) DEFAULT NULL,
  `job_order` varchar(10) DEFAULT NULL,
  PRIMARY KEY (`ticket_no`),
  UNIQUE KEY `job_order_UNIQUE` (`job_order`)
) ENGINE=InnoDB AUTO_INCREMENT=26 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `entries`
--

LOCK TABLES `entries` WRITE;
/*!40000 ALTER TABLE `entries` DISABLE KEYS */;
INSERT INTO `entries` VALUES (14,'Llao llao',NULL,'Hardware','IT Support','2026-02-25 15:26:26','llaollao@gmail.com','Not Working POS.','pending',NULL,'jo-0001'),(15,'Jollibee','09673679257','Software','IT Support','2026-02-25 15:32:12',NULL,'Software has been buggy.','pending',NULL,'jo-0002'),(16,'Tim Ho Wan','09222222222','Defective','IT Support','2026-02-25 16:05:31',NULL,'Can\'t Open device','ongoing',NULL,'jo-0003'),(17,'Mesa',NULL,'POS','Technician 2','2026-02-25 16:08:38','Mesa@gmail.com','Card payment not working','completed',NULL,'jo-0004'),(18,'Llao llao','09344345757','Hardware','Technician 1','2026-02-27 09:37:32',NULL,'Lagging UI','pending',NULL,'jo-0005'),(19,'Pizza Hut','09332332323','Technical','Technician 1','2026-02-27 10:33:45',NULL,'hang','pending',NULL,'jo-0006'),(20,'Potato Corner','09000000000','Hardware','IT Support','2026-02-27 13:27:36',NULL,'Not. Working','pending',NULL,'jo-0007'),(21,'Black Scoop','02933333333','Hardware','IT Support','2026-02-27 13:43:38','blackscoop@gmail.com','Not Opening','pending',NULL,'jo-0008'),(22,'Siomai House','3232323223','Software','IT Support','2026-02-27 16:51:36','Siomai@gmail.com','Update needed','pending',NULL,'jo-0009'),(23,'Yellow Cab','09339993333','Unit Replacement','Technician 1','2026-02-28 09:46:32','yellowcab@gmail.com','Dead pixel on POS','pending',NULL,'jo-0010'),(24,'Llao llao','09064409887','Hardware','IT Support','2026-02-28 16:58:41',NULL,'POS is not opening','pending',NULL,'jo-0011'),(25,'qdded','90909090','faef','Technician 1','2026-03-02 09:41:43',NULL,'esfsfr','pending',NULL,'jo-0012');
/*!40000 ALTER TABLE `entries` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `idusers` int NOT NULL AUTO_INCREMENT,
  `email` varchar(45) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `first_name` varchar(45) DEFAULT NULL,
  `last_name` varchar(45) DEFAULT NULL,
  `role` varchar(45) NOT NULL,
  `is_active` varchar(45) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`idusers`),
  UNIQUE KEY `email_UNIQUE` (`email`),
  UNIQUE KEY `unique_email` (`email`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `users`
--

LOCK TABLES `users` WRITE;
/*!40000 ALTER TABLE `users` DISABLE KEYS */;
INSERT INTO `users` VALUES (1,'test2@gmail.com','scrypt:32768:8:1$PM7gZHr7j9Zx1H7l$5833eda655240a9f2c6346de53c29309233b4d61d84eb73dde4e9469c0524808beb811d7c8e721ee76a613a99ebc2ef826ae676329e92d72c1322bcb24c9018e','Test1','User','end_user','1','2026-02-25 01:59:57','2026-02-27 13:34:58'),(2,'lorenzojacinto08@gmail.com','scrypt:32768:8:1$MO3dN7fOVHoP418f$5fc5d88251a2efd878edd46144455d6af65808363f0011d62dd25234d18d73adf870688920f88ed29fe7e42fa86192b65e4aa3a51712943e57127d0828e52fdd','Test2','User','end_user','1','2026-02-27 01:50:07','2026-02-27 10:27:57'),(3,'super_admin@gmail.com','scrypt:32768:8:1$WF0JlgZWceviOlJL$c2a62706bdbb2e08ffe2aa519e64850236d65d8fbc2b657261979e759d1bd9a03d0e97aee8e17e673ec7ed11e748b331a73b33096282c4e51f154162fb27be31','Super','Admin','super_admin','1','2026-02-27 02:13:38','2026-03-02 11:19:17'),(4,'user1@gmail.com','scrypt:32768:8:1$HGlTLdpSRZWCVtBh$bd7fce6c42678416e040342a93cc7c6206972a19ac219aefb17f447e086a83c51528425f0388e3413144ae177c13da0b0e580388a47f5a7fd11260752791a10c','User1','Test','admin','1','2026-02-27 03:56:12','2026-02-27 14:17:45');
/*!40000 ALTER TABLE `users` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-03-02 11:22:04